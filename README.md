# 論文をSlackに通知するApp

## 環境変数の設定

- `OPENAI_KEY`
  - Open AIより取得する必要あり
  - 従量課金が発生します．

- `CHATPDF_KEY`
  - ChatPDFのAPIキー
  - [公式サイト](https://www.chatpdf.com/docs/api/backend)より取得

- `SLACK_API_TOKEN`
  - chatbotのトークン
  - `chat:write`の権限が必要

- `SLACK_CHANNEL_NAME`
  - 投稿したいチャンネル名を記述
  - `#`を含むことに注意

## 実行方法

```bash
python main.py
```

## 参照

- [slack chatbotの作り方](https://qiita.com/odm_knpr0122/items/04c342ec8d9fe85e0fe9)