import pandas as pd
import matplotlib
# Use 'Agg' backend for headless cloud environments
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import json
import logging
import os
import base64
import sqlite3
from typing import List, Optional, Any
from pydantic import BaseModel
from openai import OpenAI

logger = logging.getLogger(__name__)

# --- Pydantic Models for Tool Outputs ---

class DataResponse(BaseModel):
    status: str
    data: Optional[list] = None
    message: Optional[str] = None

class AnalysisResponse(BaseModel):
    status: str
    analysis: Optional[str] = None
    message: Optional[str] = None

class ChartResponse(BaseModel):
    status: str
    chart_url: Optional[str] = None
    message: Optional[str] = None

class HumanInputResponse(BaseModel):
    status: str
    reason: str
    question: str

class SchemaResponse(BaseModel):
    status: str
    schema: Optional[dict] = None
    message: Optional[str] = None

# --- The Toolset Implementation ---

class DataPipelineToolset:
    def __init__(self):
        # Initialize OpenRouter client for Vision tasks
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY")
        )

    def submit_plan(self, steps: List[str]) -> dict:
        """Submit the execution plan for the data pipeline."""
        return {"status": "success", "message": "Plan accepted", "planned_steps": steps}

    def _peel_data(self, input_val: Any) -> list:
        """Internal helper to extract data from LLM outputs."""
        try:
            data = json.loads(input_val) if isinstance(input_val, str) else input_val
            if isinstance(data, dict):
                return data.get("data") or data.get("result") or []
            return data if isinstance(data, list) else []
        except:
            return []

    # --- Workspace Awareness Tool ---
    def list_files(self) -> dict:
        """Lists all files available in the current workspace directory."""
        try:
            files = os.listdir("/app")
            return {"status": "success", "files": files}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # --- NEW: Database Schema Tool ---
    def get_db_schema(self, db_name: str) -> SchemaResponse:
        """
        Returns the table names and column names for a given SQLite database.
        Use this if you are unsure about table or column names before querying.
        """
        db_path = f"/app/{db_name}"
        if not os.path.exists(db_path):
            return SchemaResponse(status="error", message=f"Database {db_name} not found.")
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            db_schema = {}
            for table in tables:
                # Get column names for each table
                cursor.execute(f"PRAGMA table_info({table});")
                db_schema[table] = [row[1] for row in cursor.fetchall()]
            
            conn.close()
            return SchemaResponse(status="success", schema=db_schema)
        except Exception as e:
            return SchemaResponse(status="error", message=f"Could not read schema: {str(e)}")

    # --- Vision Tool ---
    def analyze_image(self, image_file_name: str, prompt: str = "Describe this image and extract any relevant data.") -> AnalysisResponse:
        """Processes an image file uploaded to the workspace using Vision AI."""
        file_path = f"/app/{image_file_name}"
        
        if not os.path.exists(file_path):
            return AnalysisResponse(status="error", message=f"File {image_file_name} not found in workspace.")

        try:
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')

            response = self.client.chat.completions.create(
                model="openai/gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ],
                    }
                ],
            )
            return AnalysisResponse(status="success", analysis=response.choices[0].message.content)
        except Exception as e:
            return AnalysisResponse(status="error", message=str(e))

    # --- Database Tool ---
    def query_custom_db(self, db_name: str, query: str) -> DataResponse:
        """
        Executes a SQL query on a user-uploaded SQLite database file.
        Use this when the user asks to analyze a .db or .sqlite file.
        """
        db_path = f"/app/{db_name}"
        
        if not os.path.exists(db_path):
            return DataResponse(
                status="error", 
                message=f"File '{db_name}' not found. Ensure it was uploaded to the /app directory."
            )

        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query(query, conn)
            conn.close()
            return DataResponse(status="success", data=df.to_dict(orient="records"))
        except Exception as e:
            return DataResponse(status="error", message=f"DB Error: {str(e)}")

    # --- Dynamic Transformation Tool ---
    def transform_data(self, raw_data_json: str, strategy: str, target_column: str = "sales") -> DataResponse:
        """Cleans data using pandas. Specify 'target_column' (e.g. 'price' or 'sales') to clean."""
        try:
            data_list = self._peel_data(raw_data_json)
            df = pd.DataFrame(data_list)
            
            if strategy == "drop_corrupt" and not df.empty:
                if target_column in df.columns:
                    df[target_column] = pd.to_numeric(df[target_column], errors='coerce')
                    df = df.dropna(subset=[target_column])
                else:
                    return DataResponse(status="error", message=f"Column '{target_column}' not found in data.")
            
            return DataResponse(status="success", data=df.to_dict(orient="records"))
        except Exception as e:
            return DataResponse(status="error", message=str(e))

    # --- Dynamic Chart Tool ---
    def generate_chart(self, transformed_data_json: str, chart_type: str, x_axis: str = "region", y_axis: str = "sales") -> ChartResponse:
        """Generates a chart. Specify 'x_axis' and 'y_axis' columns (e.g. x_axis='timestamp', y_axis='price')."""
        try:
            data_list = self._peel_data(transformed_data_json)
            df = pd.DataFrame(data_list)
            
            if x_axis not in df.columns or y_axis not in df.columns:
                return ChartResponse(status="error", message=f"Required columns '{x_axis}' or '{y_axis}' missing.")

            plt.figure(figsize=(10, 6))
            if chart_type.lower() == "bar":
                plt.bar(df[x_axis], df[y_axis], color='skyblue')
            elif chart_type.lower() == "pie":
                plt.pie(df[y_axis], labels=df[x_axis], autopct='%1.1f%%')
            
            plt.title(f"{y_axis.title()} by {x_axis.title()}")
            plt.xticks(rotation=45) 
            plt.tight_layout()
            
            file_name = "output_chart.png"
            plt.savefig(f"/app/{file_name}")
            plt.close()
            return ChartResponse(status="success", chart_url=file_name)
        except Exception as e:
            return ChartResponse(status="error", message=str(e))

    def request_human_input(self, reason: str, question: str) -> HumanInputResponse:
        """Pauses the workflow to ask the user a question."""
        return HumanInputResponse(status="paused", reason=reason, question=question)

def get_tools():
    ts = DataPipelineToolset()
    return {
        "submit_plan": ts.submit_plan,
        "list_files": ts.list_files,
        "get_db_schema": ts.get_db_schema,
        "analyze_image": ts.analyze_image,
        "query_custom_db": ts.query_custom_db,
        "transform_data": ts.transform_data,
        "generate_chart": ts.generate_chart,
        "request_human_input": ts.request_human_input
    }