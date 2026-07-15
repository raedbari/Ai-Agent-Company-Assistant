from pydantic import BaseModel, Field


class KnowledgeSource(BaseModel):
    source_id: str
    title_ar: str


class KnowledgeModelAnswer(BaseModel):
    answer_ar: str
    source_ids: list[str] = Field(default_factory=list)
    sufficient_context: bool


class KnowledgeAnswerResult(BaseModel):
    text: str
    sources: list[KnowledgeSource] = Field(default_factory=list)
    sufficient_context: bool