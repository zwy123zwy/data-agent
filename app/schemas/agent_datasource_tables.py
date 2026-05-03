"""AgentDatasourceTables Pydantic Schema"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class AgentDatasourceTablesCreate(BaseModel):
    agent_datasource_id: int
    table_name: str


class AgentDatasourceTablesResponse(BaseModel):
    id: int
    agent_datasource_id: int
    table_name: str
    create_time: datetime
    update_time: datetime

    model_config = ConfigDict(from_attributes=True)
