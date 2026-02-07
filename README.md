# TeamRank Prototype

这是一个最小可运行的原型（Flask + SQLite），演示基本流程：用户配置、发起 Lobby、加入队伍、提交证明并进行评分（评分需要先有提交）。

运行步骤：

1. 创建并激活 Python 虚拟环境（可选但推荐）

```bash
python -m venv venv
venv\Scripts\activate
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 填充示例数据：

```bash
python seed_db.py
```

4. 启动应用：

```bash
python app.py
```

5. 打开浏览器访问 http://127.0.0.1:5000/ 查看最小前端示例。

API 概览：
- `GET /api/users`  列表用户
- `POST /api/users` 创建用户 JSON {name, major, year}
- `GET /api/lobbies` 列表大厅
- `POST /api/lobbies` 创建大厅 JSON {title, contest_link, leader_id}
- `POST /api/lobbies/<id>/join` 加入大厅 JSON {user_id}
- `POST /api/teams/<id>/submit` 提交证明 JSON {proof: 'url or text'}
- `POST /api/teams/<id>/ratings` 评分（要求已有提交） JSON {rater_id, target_user_id, contribution, communication, would_work_again, comment}
