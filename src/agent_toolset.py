import pandas as pd
import matplotlib
# Use 'Agg' backend for headless Docker environments
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import json
import logging
from typing import List, Optional, Any
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# --- Pydantic Models for Tool Outputs ---

class DataResponse(BaseModel):
    status: str
    data: Optional[list] = None
    message: Optional[str] = None

class ChartResponse(BaseModel):
    status: str
    chart_url: Optional[str] = None
    message: Optional[str] = None

class ReportResponse(BaseModel):
    status: str
    report_content: Optional[str] = None

class EmailResponse(BaseModel):
    status: str
    message: str

class HumanInputResponse(BaseModel):
    status: str
    reason: str
    question: str

# --- The Toolset Implementation ---

class DataPipelineToolset:
    def __init__(self):
        self.fetch_attempts = 0

    def submit_plan(self, steps: List[str]) -> dict:
        """Submit the execution plan for the data pipeline."""
        return {"status": "success", "message": "Plan accepted", "planned_steps": steps}

    def fetch_data(self, source: str, query: str) -> DataResponse:
        """Fetches raw data. Simulates a 429 Rate Limit on the first attempt."""
        self.fetch_attempts += 1
        
        if self.fetch_attempts == 1:
            logger.warning("Simulating 429 Rate Limit Error")
            return DataResponse(status="error", message="429 Too Many Requests from v2_api")
        
        raw_data = [
            {"region": "North", "sales": 15000, "status": "clean"},
            {"region": "South", "sales": 12000, "status": "clean"},
            {"region": "East", "sales": "ERROR_NAN", "status": "corrupt"}
        ]
        return DataResponse(status="success", data=raw_data)

    def _peel_data(self, input_val: Any) -> list:
        """Internal helper to extract a list of data from wrapped LLM inputs."""
        try:
            # If it's a string, try to parse it
            data = json.loads(input_val) if isinstance(input_val, str) else input_val
            
            # If the LLM passed the whole response dictionary, grab just the 'data' part
            if isinstance(data, dict):
                if "data" in data:
                    return data["data"]
                if "result" in data:
                    return data["result"]
            
            # If it's already a list, we're good
            if isinstance(data, list):
                return data
                
            return []
        except:
            return []

    def transform_data(self, raw_data_json: str, strategy: str) -> DataResponse:
        """Cleans data using pandas based on a strategy."""
        try:
            # Peel the data out of potential wrappers
            data_list = self._peel_data(raw_data_json)
            if not data_list:
                return DataResponse(status="error", message="Could not find valid data list in input")

            df = pd.DataFrame(data_list)
            
            if strategy == "drop_corrupt":
                # Ensure sales is numeric and drop the NaNs created by ERROR_NAN
                df['sales'] = pd.to_numeric(df['sales'], errors='coerce')
                df = df.dropna(subset=['sales'])
            
            clean_json = df.to_json(orient="records")
            return DataResponse(status="success", data=json.loads(clean_json))
        except Exception as e:
            logger.error(f"Pandas transformation failed: {e}")
            return DataResponse(status="error", message=f"Pandas transformation failed: {str(e)}")

    def generate_chart(self, transformed_data_json: str, chart_type: str) -> ChartResponse:
        """Generates a real PNG chart using matplotlib."""
        try:
            # Peel the data out of potential wrappers
            data_list = self._peel_data(transformed_data_json)
            if not data_list:
                return ChartResponse(status="error", message="No data available to generate chart")

            df = pd.DataFrame(data_list)
            
            plt.figure(figsize=(8, 6))
            if chart_type.lower() == "bar":
                plt.bar(df['region'], df['sales'], color='skyblue')
            elif chart_type.lower() == "pie":
                plt.pie(df['sales'], labels=df['region'], autopct='%1.1f%%')
            else:
                return ChartResponse(status="error", message=f"Unsupported chart: {chart_type}")

            plt.title(f"Sales Distribution ({chart_type.title()})")
            
            # Explicit path to ensure it lands in the mapped volume
            file_path = "/app/pipeline_chart.png"
            plt.savefig(file_path)
            plt.close()

            logger.info(f"Chart successfully saved to {file_path}")
            return ChartResponse(status="success", chart_url="pipeline_chart.png")
        except Exception as e:
            logger.error(f"Matplotlib failed: {e}")
            return ChartResponse(status="error", message=f"Matplotlib failed: {str(e)}")

    def compose_report(self, summary_text: str, chart_url: str) -> ReportResponse:
        """Composes a markdown report."""
        report = f"# Pipeline Summary Report\n\n{summary_text}\n\n![Chart]({chart_url})"
        return ReportResponse(status="success", report_content=report)

    def dispatch_email(self, report_content: str, recipient: str) -> EmailResponse:
        """Simulates sending the report via email."""
        logger.info(f"Emailing report to {recipient}")
        return EmailResponse(status="success", message=f"Email successfully sent to {recipient}")

    def request_human_input(self, reason: str, question: str) -> HumanInputResponse:
        """Pauses the workflow to ask the user a question."""
        return HumanInputResponse(status="paused", reason=reason, question=question)

    def escalate(self, reason: str, failed_step: str) -> dict:
        """Halt the workflow and notify the user of a critical failure."""
        return {"status": "escalated", "message": f"Workflow halted at {failed_step}: {reason}"}

def get_tools():
    ts = DataPipelineToolset()
    return {
        "submit_plan": ts.submit_plan,
        "fetch_data": ts.fetch_data,
        "transform_data": ts.transform_data,
        "generate_chart": ts.generate_chart,
        "compose_report": ts.compose_report,
        "dispatch_email": ts.dispatch_email,
        "request_human_input": ts.request_human_input,
        "escalate": ts.escalate
    }