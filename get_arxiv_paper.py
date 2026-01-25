# coding: utf-8
import arxiv
import os
import json
import requests
import time
from openai import OpenAI

model_name = os.getenv("MODEL_NAME")
print(f"model_name: {len(model_name)}")
base_url = os.getenv("BASE_URL")
api_key = os.getenv("API_KEY")

bot_url = os.getenv("BOT_URL")
max_result = os.getenv("MAX_RESULT", 20)

translateion_prompt = "你是一个专业的英文论文摘要翻译助手，擅长翻译为中文。请将以下论文摘要翻译成中文，确保内容准确流畅。"

class Model:
    def __init__(self, base_url, api_key, model_name, translation_prompt):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name
        self.translation_prompt = translation_prompt

    def generate(self, msg, temperature = 1):
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.translation_prompt},
                {"role": "user", "content": msg}
            ],
            temperature=temperature,
            stream=False
        )
        text = response.choices[0].message.content.strip()
        return text
    

class Bot:
    def __init__(self, url, type="feishu"):
        self.url = url
        self.type = type

    def build_content(self, paper: dict):
        content = f"""[{paper['entry_id']}]({paper['entry_id']})
{paper['translated_summary']}
"""
        return content

    def send_message_feishu(self, paper: dict, msg_id):
        card_data = {
            "config": {
                "enable_forward": True,
                "update_multi": True
            },
            "header": {
                "template": "green",
                "title": {
                    "tag": "plain_text",
                    "content": msg_id + '\n' + paper['title']
                }
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": self.build_content(paper)
                }
            ]
        }
        card = json.dumps(card_data)
        body = json.dumps({"msg_type": "interactive", "card":card})
        headers = {"Content-Type":"application/json"}

        try:
            response = requests.post(url=self.url, data=body, headers=headers, timeout=10)
            print(response.status_code, response.text)
        except Exception as e:
            print(f"send message failed: {e}")

    def send_message(self, paper, msg_id):
        if self.type == "feishu":
            self.send_message_feishu(paper, msg_id)
        else:
            print("unsupported bot type")


def search_arxiv(query: str = 'cat:cs.IR', max_results: int = 20):
    # 搜索参数
    search = arxiv.Search(
        query=query,
        max_results=int(max_results),
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )

    papers = []

    for result in search.results():
        papers.append(
            {
                "title": result.title,
                "summary": result.summary.strip(),
                "entry_id": result.entry_id,
                "pub_date": result.published.strftime("%Y-%m-%d"),
            }
        )
    return papers


def depulicate_papers(papers, history_data):
    # compare latest 50
    recent_history_id = set([elem['entry_id'] for elem in history_data[-50:]])
    unique_papers = []
    for paper in papers:
        if paper['entry_id'] not in recent_history_id:
            unique_papers.append(paper)
    return unique_papers


if __name__ == "__main__":
    model = Model(base_url=base_url, 
                  api_key=api_key, 
                  model_name=model_name, 
                  translation_prompt=translateion_prompt)
    bot = Bot(bot_url, type="feishu")

    # load history papers
    history_paper = json.load(open("papers.json", "r"))
    
    # search new papers
    query = 'cat:cs.IR'
    print(f"search arxiv with query: {query}, max_results: {max_result}")
    papers = search_arxiv(query=query, max_results=max_result)
    unique_papers = depulicate_papers(papers, history_paper)

    # translate summary and send msg
    for index, paper in enumerate(unique_papers):
        translated_summary = model.generate(paper['summary'], temperature=1)
        paper['translated_summary'] = translated_summary
        bot.send_message(paper, msg_id=f"Paper {index+1}, pub_date: {paper['pub_date']}")
        time.sleep(10)

    # save
    history_paper.extend(unique_papers)
    json.dump(history_paper, open("papers.json", "w"), indent=4, ensure_ascii=False)
        