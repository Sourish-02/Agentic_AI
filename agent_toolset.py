import json
from typing import Any, List, Optional
from pydantic import BaseModel

# ==========================================
# PYDANTIC RESPONSE MODELS
# ==========================================

class FetchResponse(BaseModel):
    status: str
    data: Optional[List[dict]] = None
    message: Optional[str] = None
    code: Optional[int] = None

class TransformResponse(BaseModel):
    status: str
    transformed_data: Optional[List[dict]] = None
    count: Optional[int] = None
    message: Optional[str] = None

class ChartResponse(BaseModel):
    status: str
    chart_url: Optional[str] = None
    message: Optional[str] = None

class ReportResponse(BaseModel):
    status: str
    report_content: Optional[str] = None
    message: Optional[str] = None

class DispatchResponse(BaseModel):
    status: str
    message: str

class EscalateResponse(BaseModel):
    status: str
    message: str


# ==========================================
# TOOLSET IMPLEMENTATION
# ==========================================

class DataPipelineToolset:
    """Tools for fetching, transforming data, and generating reports."""

    def __init__(self):
        # State tracker to simulate transient failures
        self.fetch_attempts = 0

    def fetch_data(self, source: str, query: str) -> FetchResponse:
        """
        Fetches data from a specified source.
        
        Args:
            source: The API or database source (e.g., 'sales_db', 'legacy_api', 'v2_api').
            query: The data query or timeframe.
        """
        self.fetch_attempts += 1
        
        if self.fetch_attempts == 1:
            return FetchResponse(
                status="error", 
                code=429, 
                message="Rate limit exceeded. Try again."
            )
            
        if source == "legacy_api":
             return FetchResponse(
                 status="error", 
                 message="Source 'legacy_api' is deprecated. Use 'v2_api'."
             )

        mock_data = [
            {"region": "North", "sales": 15000, "status": "clean"},
            {"region": "South", "sales": 12000, "status": "clean"},
            {"region": "East", "sales": "ERROR_NAN", "status": "corrupt"} 
        ]
        return FetchResponse(status="success", data=mock_data)

    def transform_data(self, raw_data_json: str, strategy: str = "standard") -> TransformResponse:
        """
        Cleans and transforms raw data.
        
        Args:
            raw_data_json: The JSON string of data to transform.
            strategy: 'standard' or 'drop_corrupt'.
        """
        try:
            data = json.loads(raw_data_json)
            if not isinstance(data, list):
                return TransformResponse(status="error", message="Expected a list of records.")

            cleaned_data = []
            for row in data:
                if row.get("status") == "corrupt":
                    if strategy == "standard":
                        return TransformResponse(
                            status="error", 
                            message="Malformed data encountered. Use strategy='drop_corrupt' to bypass."
                        )
                    else:
                        continue 
                cleaned_data.append(row)
                
            return TransformResponse(
                status="success", 
                transformed_data=cleaned_data, 
                count=len(cleaned_data)
            )
        except Exception as e:
            return TransformResponse(status="error", message=f"JSON parsing failed: {str(e)}")

    def generate_chart(self, transformed_data_json: str, chart_type: str) -> ChartResponse:
        """
        Generates a summary chart.
        
        Args:
            transformed_data_json: The JSON string of clean data.
            chart_type: e.g., 'bar', 'line', 'pie'.
        """
        if chart_type not in ["bar", "line", "pie"]:
            return ChartResponse(status="error", message="Unsupported chart type.")
            
        return ChartResponse(
            status="success", 
            chart_url=f"https://mock-charts.com/generated_{chart_type}_chart.png"
        )

    def compose_report(self, summary_text: str, chart_url: str) -> ReportResponse:
        """
        Composes a formatted markdown report.
        
        Args:
            summary_text: Brief text summary of the data.
            chart_url: The URL of the generated chart.
        """
        report = f"# Pipeline Summary Report\n\n{summary_text}\n\n![Chart]({chart_url})"
        return ReportResponse(status="success", report_content=report)

    def dispatch_email(self, report_content: str, recipient: str) -> DispatchResponse:
        """
        Dispatches the composed report to the recipient.
        
        Args:
            report_content: The formatted markdown report.
            recipient: The email address.
        """
        if "@" not in recipient:
            return DispatchResponse(status="error", message="Invalid email format.")
            
        return DispatchResponse(status="success", message=f"Email successfully sent to {recipient}")

    def escalate(self, reason: str, failed_step: str) -> EscalateResponse:
        """
        Triggers an escalation if a step fails after maximum retries.
        
        Args:
            reason: Why the workflow is being escalated.
            failed_step: The name of the step that failed.
        """
        return EscalateResponse(
            status="escalated", 
            message=f"Workflow halted at {failed_step}. Human intervention required: {reason}"
        )

    def get_tools(self) -> dict[str, Any]:
        return {
            'fetch_data': self.fetch_data,
            'transform_data': self.transform_data,
            'generate_chart': self.generate_chart,
            'compose_report': self.compose_report,
            'dispatch_email': self.dispatch_email,
            'escalate': self.escalate,
        }
