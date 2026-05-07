"""
科研自动化助手 — 统一启动脚本。

用法：
  python run.py api      — 启动 FastAPI 后端服务
  python run.py ui       — 启动 Streamlit 前端界面
  python run.py init     — 初始化数据库
  python run.py test     — 运行测试
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def init_database():
    """初始化数据库。"""
    print("=" * 60)
    print("初始化数据库...")
    print("=" * 60)

    from src.database.connection import get_db
    from src.utils.logger import init_logging

    init_logging()
    db = get_db()
    db.initialize()

    # 检查表
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    print(f"\n已创建 {len(tables)} 个表:")
    for row in tables:
        print(f"  - {row[0]}")

    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")
    views = cursor.fetchall()
    print(f"\n已创建 {len(views)} 个视图:")
    for row in views:
        print(f"  - {row[0]}")

    conn.close()
    print(f"\n数据库路径: {db.db_path}")
    print("数据库初始化完成。")


def start_api():
    """启动 FastAPI 服务。"""
    print("=" * 60)
    print("启动 FastAPI 后端服务 (http://localhost:8000)...")
    print("API 文档: http://localhost:8000/docs")
    print("=" * 60)

    from uvicorn import run
    run("api.main:app", host="0.0.0.0", port=8000, reload=True)


def start_ui():
    """启动 Streamlit 前端界面。"""
    import subprocess
    import socket

    port = 8501

    # 端口占用检查
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    port_in_use = sock.connect_ex(("localhost", port)) == 0
    sock.close()
    if port_in_use:
        print(f"[警告] 端口 {port} 已被占用，Streamlit 将尝试使用其他端口。")
        print(f"  可使用 streamlit run ui/app.py --server.port <其他端口> 手动指定。")

    print("=" * 60)
    print(f"启动 Streamlit 前端界面 (http://localhost:{port})...")
    print("=" * 60)

    ui_path = str(PROJECT_ROOT / "ui" / "app.py")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", ui_path, "--server.port", str(port)],
        cwd=str(PROJECT_ROOT),
    )


def run_tests():
    """运行测试。"""
    print("=" * 60)
    print("运行测试...")
    print("=" * 60)

    import pytest
    test_dir = str(PROJECT_ROOT / "tests")
    sys.exit(pytest.main([test_dir, "-v"]))


def print_help():
    """打印帮助信息。"""
    print("""
科研自动化助手 — 启动脚本

用法:
  python run.py <command>

命令:
  api       启动 FastAPI 后端服务 (端口 8000)
  ui        启动 Streamlit 前端界面 (端口 8501)
  init      初始化数据库 (data/paper.db)
  test      运行单元测试
  help      显示此帮助信息
""")


# ============================================================================
# 主入口
# ============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)

    command = sys.argv[1].lower()

    commands = {
        "api": start_api,
        "ui": start_ui,
        "init": init_database,
        "test": run_tests,
        "help": print_help,
    }

    if command in commands:
        commands[command]()
    else:
        print(f"未知命令: {command}")
        print_help()
        sys.exit(1)
