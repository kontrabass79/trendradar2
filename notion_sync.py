import os
import yaml
import feedparser
import requests
from notion_client import Client

# 1. 从 GitHub Secrets 自动读取环境变量
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
AI_API_KEY = os.environ.get("AI_API_KEY")

# 2. 改为 Groq 官方的 API 终点
AI_API_URL = "https://api.groq.com/openai/v1/chat/completions"


notion = Client(auth=NOTION_TOKEN)

def get_rss_summary(urls):
    """抓取每个领域最新的几条新闻"""
    text_summary = ""
    for url in urls[:3]: # 每个领域只取前3个源防爆
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]: # 每个源取前3条
            text_summary += f"标题: {entry.title}\n简介: {entry.get('summary', '')[:100]}\n\n"
    return text_summary

def ai_wash_article(domain_name, raw_text):
    """调用 Groq 大模型进行今日头条风格洗稿"""
    headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
    prompt = f"你是一个头条自媒体爆款主笔。请根据以下关于【{domain_name}】的资讯：\n{raw_text}\n" \
             f"写一篇500-700字的中文博客。要求：1.标题极具悬念和吸引力。2.段落短小，符合中国人阅读习惯。\n" \
             f"请严格按此格式输出，不要有额外解释：\n【标题】你的爆款标题\n【正文】你的正文内容"
             
    payload = {
        "model": "llama-3.3-70b-versatile", # Groq 极速免费的高级模型
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    res = requests.post(AI_API_URL, json=payload, headers=headers).json()
    reply = res['choices'][0]['message']['content']
    
    # 简单切分标题和正文
    try:
        title = reply.split("【正文】")[0].replace("【标题】", "").strip()
        content = reply.split("【正文】")[-1].strip()
    except:
        title = f"今日必读：{domain_name}重大突破！"
        content = reply
    return title, content

def push_to_notion(title, content, tag):
    """将文章以羊皮纸样式发送到Notion"""
    img_url = f"https://picsum.photos{tag}" 
    paragraphs = content.split("\n")
    
    children_blocks = [
        {"object": "block", "type": "image", "image": {"type": "external", "external": {"url": img_url}}}
    ]
    
    # 用 brown_background 伪造羊皮纸背景色
    for p in paragraphs:
        if not p.strip(): continue
        children_blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": p.strip()}}],
                "icon": {"type": "emoji", "emoji": "📜"},
                "color": "brown_background" 
            }
        })
        
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "Name": {"title": [{"text": {"content": title}}]},
            "分类": {"multi_select": [{"name": tag}]}
        },
        children=children_blocks
    )

def main():
    # 临时写死几个测试源，确保 100% 成功。后续可以在 config 文件夹中优化
    config = {
        "sources": {
            "ai": ["https://arxiv.org", "https://hnrss.org"],
            "tech": ["https://linux.do", "https://theverge.com"],
            "money": ["https://producthunt.com", "https://ezindie.com"]
        }
    }
    
    tasks = [("ai", "人工智能"), ("tech", "科技领域"), ("money", "网赚领域")]
    for key, tag in tasks:
        try:
            urls = config["sources"].get(key, [])
            raw_text = get_rss_summary(urls)
            if not raw_text: continue
            title, content = ai_wash_article(tag, raw_text)
            push_to_notion(title, content, tag)
            print(f"🎉 {tag} 文章发布成功！")
        except Exception as e:
            print(f"❌ {tag} 失败: {e}")

if __name__ == "__main__":
    main()
