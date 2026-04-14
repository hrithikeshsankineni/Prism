from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str = ""
    tavily_api_key: str = ""

    # Model allocation
    groq_planner_model: str = "llama-3.3-70b-versatile"
    groq_research_model: str = "llama-3.1-8b-instant"   # fast, free; kept under 6k TPM with max_tokens=1024
    groq_synthesis_model: str = "llama-3.3-70b-versatile"
    groq_critic_model: str = "llama-3.3-70b-versatile"
    groq_eval_model: str = "llama-3.1-8b-instant"       # fast, free; eval output is small

    # Agent execution
    agent_timeout_seconds: int = 120
    max_research_agents: int = 3                    # 5 agents blows the RPM budget
    agent_stagger_seconds: float = 6.0              # more spacing = fewer burst 429s

    # Rate limiting
    groq_max_concurrent_requests: int = 3
    groq_rpm_limit: int = 25
    groq_retry_max_attempts: int = 3
    groq_retry_base_delay: float = 2.0

    # Tavily
    tavily_max_results: int = 5

    # RAG
    chroma_persist_dir: str = "./chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
