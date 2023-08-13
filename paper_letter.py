# arXivから論文を取得し，自動的に通知するコード

import datetime as dt
import os
import time
from typing import Set
import requests
import json

import arxiv
import openai
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# OpenAIのAPIキーを設定
openai.api_key = os.environ.get("OPENAI_KEY")

# ChatPDFのAPIキーを設定
chatpdf_key = os.environ.get("CHATPDF_KEY")


# Slack APIトークン
SLACK_API_TOKEN = os.environ.get("SLACK_API_TOKEN")

# Slackに投稿するチャンネル名を指定する
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_NAME")

# Slack APIクライアントを初期化する
client = WebClient(token=SLACK_API_TOKEN)

# queryを用意
QUERY_TEMPLATE = "%28 ti:%22{}%22 OR abs:%22{}%22 %29 AND submittedDate: [{} TO {}]"

# 投稿するカテゴリー
CATEGORIES = {
    "cs.AI",  # 人工知能
    "cs.AR",  # ハードウェアアーキテクチャ
    "cs.CV",  # コンピュータビジョン
    "cs.DC",  # 分散・並列・クラスタコンピューティング
    "cs.ET",  # 新技術
    "cs.HC",  # フーマンコンピュータインタラクション
    "cs.IT",  # 情報理論
    "cs.LG",  # 機械学習
    "cs.NE",  # ニューラルネットワーク
    "cs.OH",  # その他のコンピュータサイエンス
    "cs.RO",  # ロボティクス
    "cs.SD",  # サウンド

    "eess.IV",  # image and video processing
    "eess.SP",  # signal processing
}

SYSTEM = """
### 指示 ###
論文の内容を理解した上で，重要なポイントを箇条書きで3点書いてください。

### 箇条書きの制約 ###
- 最大3個
- 日本語
- 箇条書き1個を50文字以内

### 対象とする論文の内容 ###
{text}

### 出力形式 ###
タイトル(和名)

- 箇条書き1
- 箇条書き2
- 箇条書き3
"""

# パラメータ
MODEL_NAME = "gpt-3.5-turbo"
TEMPERATURE = 0.25
MAX_RESULT = 10
N_DAYS = 1


# def get_summary(result: arxiv.Result) -> str:
#     """
#     論文の要約を取得
#     Args:
#         result: arXivの検索結果
#     Returns:
#         message: 要約
#     """
#     text = f"title: {result.title}\nbody: {result.summary}"
#     cnt = 0
#     while True:
#         try:
#             response = openai.ChatCompletion.create(
#                 model=MODEL_NAME,
#                 messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
#                 temperature=TEMPERATURE,
#             )
#             break
#         except Exception as e:
#             time.sleep(20)
#             cnt += 1
#             # 3回失敗したらエラーを吐く
#             if cnt == 3:
#                 raise e

#     time.sleep(5)
#     summary = response["choices"][0]["message"]["content"]
#     title_en = result.title
#     title, *body = summary.split("\n")
#     body = "\n".join(body)
#     date_str = result.published.strftime("%Y-%m-%d %H:%M:%S")
#     message = f"発行日: {date_str}\n{result.entry_id}\n{title_en}\n{title}\n{body}\n"

#     return message


def get_summary(result: arxiv.Result) -> str:
    """
    論文の要約を取得(ChatPDF)
    Args:
        result: arXivの検索結果
    Returns:
        message: 要約
    """

    headers = {
        'x-api-key': chatpdf_key,
        'Content-Type': 'application/json'
    }

    # PDFファイルを指定してチャットの初期設定を行う
    data = {'url': result.pdf_url}
    response = requests.post(
        'https://api.chatpdf.com/v1/sources/add-url', headers=headers, json=data)

    if response.status_code == 200:
        print('Source ID:', response.json()['sourceId'])
    else:
        print('Status:', response.status_code)
        print('Error:', response.text)

    # 実際のチャット開始
    # 要約の作成
    data = {
        'sourceId': response.json()['sourceId'],
        'messages': [
            {
                'role': "user",
                'content': "本論文を要約してください",
            }
        ]
    }

    # 要約されたメッセージを取得
    chat_request = requests.post('https://api.chatpdf.com/v1/chats/message', headers=headers, json=data)
    try:
        # str型で，json形式の出力が返ってくるため，扱いやすいように整形
        summary_json = json.loads(chat_request.text)
        summary = summary_json["content"]
    except Exception as e:
        print(e)
        summary = "要約に失敗しました．"

    time.sleep(2)

    # 落合フォーマットで要約
    summary_o = ""
    question_list = [
        "論文を3行で要約してください．",
        "関連研究と比べてどこがすごいですか？",
        "提案手法の最も重要なポイントは何ですか？",
        "提案手法の有効性をどのように検証しましたか？",
        "本論文に残された課題はなんですか？",
        # "参考文献のうち，本論文とのつながりが特に深い論文のタイトルをいくつか教えてください"
    ]

    for id, question in enumerate(question_list):
        data = {
            'sourceId': response.json()['sourceId'],
            'messages': [
                {
                    'role': "user",
                    'content': question,
                }
            ]
        }

        # 要約されたメッセージを取得
        chat_request = requests.post('https://api.chatpdf.com/v1/chats/message', headers=headers, json=data)
        try:
            # str型で，json形式の出力が返ってくるため，扱いやすいように整形
            summary_json = json.loads(chat_request.text)
            summary_o += str(id + 1) + ". " + question + ": \n" + summary_json["content"] + "\n\n"
        except Exception as e:
            print(e)
            summary_o += question + ": " + "この回答生成に失敗しました．"

    # チャットの終了処理
    data = {
        'sources': [response.json()['sourceId']],
    }

    try:
        response = requests.post(
            'https://api.chatpdf.com/v1/sources/delete', json=data, headers=headers)
        response.raise_for_status()
        print('Success')
    except requests.exceptions.RequestException as error:
        print('Error:', error)
        print('Response:', error.response.text)

    return summary, summary_o


def job(keyword: str, paper_hash: Set[str], is_debug: bool = False) -> Set[str]:
    """
    論文の要約をして，Slackに投稿する
    Args:
        keyword: 検索キーワード
        paper_hash: 既に投稿済みの論文のタイトル
        is_debug: デバッグモード
    Returns:
        paper_hash: 既に投稿済みの論文のタイトル
    """
    # 日付の設定
    # arXivの更新頻度を加味して，1週間前の論文を検索
    today = dt.datetime.today() - dt.timedelta(days=7)
    base_date = today - dt.timedelta(days=N_DAYS)
    query = QUERY_TEMPLATE.format(keyword, keyword, base_date.strftime("%Y%m%d%H%M%S"), today.strftime("%Y%m%d%H%M%S"))
    search = arxiv.Search(
        query=query,  # 検索クエリ
        max_results=MAX_RESULT * 3,  # 取得する論文数の上限
        sort_by=arxiv.SortCriterion.SubmittedDate,  # 論文を投稿された日付でソートする
        sort_order=arxiv.SortOrder.Descending,  # 新しい論文から順に取得する
    )

    # searchの結果をリストに格納
    result_list = []
    for result in search.results():
        # 既に投稿済みの論文は除く
        if result.title in paper_hash:
            continue
        # カテゴリーに含まれない論文は除く
        if len((set(result.categories) & CATEGORIES)) == 0:
            continue

        if is_debug:
            print(result.published)
            print(result.title)
        result_list.append(result)
        paper_hash.add(result.title)

        # 最大件数に到達した場合は，そこで打ち止め
        if len(result_list) == MAX_RESULT:
            break

    if len(result_list) == 0:
        # 初期メッセージ
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"{'=' * 40}\n{keyword}に関する論文は有りませんでした！\n{'=' * 40}",
        )
        return paper_hash
    else:
        # 初期メッセージ
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"{'=' * 40}\n{keyword}に関する論文は{len(result_list)}本ありました！\n{'=' * 40}",
        )

    # 論文情報をSlackに投稿する
    for i, result in enumerate(result_list, start=1):
        try:
            # Slackに投稿するメッセージを組み立てる
            # message = f"{keyword}: {i}本目\n" + get_summary(result)
            message = f"{keyword}: {i}本目\n タイトル：{result.title}\n リンク：{result}"

            # Slackにメッセージを投稿する
            response = client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
            summary, summary_o = get_summary(result)
            if is_debug:
                print(summary)
                print(summary_o)
            _ = client.chat_postMessage(channel=SLACK_CHANNEL, text=summary, thread_ts=response['ts'])
            _ = client.chat_postMessage(channel=SLACK_CHANNEL, text=summary_o, thread_ts=response['ts'])
            print(f"Message posted: {response['ts']}")

        except SlackApiError as e:
            print(f"Error posting message: {e}")
        time.sleep(5)

    return paper_hash


def main():
    """
    Cloud Functionsで実行するメイン関数
    """
    keyword_list = [
        "LLM",
        "Robotics",
        "Autonomous driving",
        "FPGA",
    ]

    paper_hash = set()
    for keyword in keyword_list:
        paper_hash = job(keyword, paper_hash, is_debug=False)


if __name__ == "__main__":
    main()
