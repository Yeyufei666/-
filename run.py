"""CampusEvent 启动入口。

运行：python run.py
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # 绑定 0.0.0.0，端口优先取环境变量 PORT（云部署需要），本地默认 5000
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
