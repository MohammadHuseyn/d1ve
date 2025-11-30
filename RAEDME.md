# What is d1ve?
d1ve is a vmess connection mangaer that provides vmess connection with subscription
# How to use?
1. clone the repo
2. `docker compose up -d --build`
3. `python -m venv .venv`
4. `source .venv/bin/activate`
5. pip install python-dotenv
6. python vmess_manager.py
7. use commands like add, get, clear, ...
8. add the subscription link (you can see it when you run step 6) to the v2ray client.