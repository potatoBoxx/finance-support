import os

def test_requirements_file_exists_and_contains_dependencies():
    assert os.path.exists("requirements.txt")
    with open("requirements.txt", encoding="utf-8") as f:
        content = f.read().lower()
    for pkg in ["streamlit", "pandas", "supabase", "yfinance", "requests", "pytest"]:
        assert pkg in content

def test_streamlit_config_exists():
    assert os.path.exists(".streamlit/config.toml")
    with open(".streamlit/config.toml", encoding="utf-8") as f:
        content = f.read()
    assert "[theme]" in content
    assert "dark" in content

def test_secrets_template_exists():
    assert os.path.exists(".streamlit/secrets.toml.example")
    with open(".streamlit/secrets.toml.example", encoding="utf-8") as f:
        content = f.read()
    assert "SUPABASE_URL" in content
    assert "SUPABASE_KEY" in content

def test_style_css_exists():
    assert os.path.exists("assets/style.css")
    with open("assets/style.css", encoding="utf-8") as f:
        content = f.read()
    assert "badge-stop-loss" in content
    assert "overflow-x: hidden" in content

def test_schema_sql_exists():
    assert os.path.exists("schema.sql")
    with open("schema.sql", encoding="utf-8") as f:
        content = f.read()
    assert "CREATE TABLE IF NOT EXISTS users" in content
    assert "CREATE TABLE IF NOT EXISTS portfolio_items" in content
