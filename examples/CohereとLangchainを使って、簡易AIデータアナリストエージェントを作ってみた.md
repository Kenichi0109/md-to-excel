# はじめに
皆さん、こんにちは。
突然ですが、Cohereという企業をご存じですか？？

[Cohere](https://cohere.com/)（kōˈhir）とは、エンタープライズ向けにLLM（大規模言語モデル）を提供するカナダ発の多国籍テクノロジー企業です。最近では、富士通がCohereと戦略的パートナーシップを結んで、プライベート環境で利用できる日本語LLM「[Takane](https://pr.fujitsu.com/jp/news/2024/07/16.html)」（仮称）の共同開発を開始しました（2024/7/16）。

そんなCohereですが、ドキュメントがとても優れていることでも話題です。

https://qiita.com/sergicalsix/items/d5c7a0a420a213309bfc

https://x.com/hAru_mAki_ch/status/1776272185893822725

今回は、そのドキュメント中の[Cookbooks](https://docs.cohere.com/page/cookbooks)（実装ガイドが色々まとまってる）における以下のページを参照して、企業の売上高成長率を分析する**簡単なAIデータアナリストエージェントを作成しましたので、作成方法の詳細と使用した後の感想を共有**しようと思います。

以下、参照ページ

https://docs.cohere.com/page/data-analyst-agent

（初めての記事作成で至らぬ部分があるかもしれませんが、その際にはご指摘や補足していただけると助かります:bow:）

# 構成と処理の流れ
参照ページにも記載がありますが、自身でも整理したアーキテクチャを以下に示します。

![diagram-export-2024-8-11-17_50_27.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3578596/33d73ec6-292d-9d33-82b1-09880b9bffd7.png)

1. AIエージェント(Data Analyst Agent)はユーザーからプロンプト（指示文）を受け取ります
1. LLMにプロンプトを渡す前に、[**Prompt Template**](https://book.st-hakky.com/data-science/langchain-prompttemplate/)によりプロンプトを整形します
1. **LLM**にプロンプトを渡して処理してもらいます
1. プロンプトの要求に答えるため、エージェントは次に実行すべきツールを選択します。インターネット検索が必要なときは**Web Search**を使い、Pythonコードの実行（データ計算やグラフ作成など）が必要なときは**Python Interpreter**を使います
1. 最後に、AIエージェントがユーザーにレスポンスを返却します

# 実装する前の準備
今回、LLMにはCohereのCommand R+を用い、Web Searchツールには[**Tavily**](https://tavily.com/)（AIエージェント専用の検索エンジン）を用います。

それぞれAPIを取得する必要があります。制限ありますがどちらも無料で使えます！！

*Cohere API*
https://dashboard.cohere.com/api-keys
*Tavily API*
https://app.tavily.com/home

また、Langchainのライブラリ導入が必要です。ターミナルから以下を実行してください。
```
! pip install langchain langchain_cohere langchain_experimental
```
# 実装
では、実装に入ります。
以下のコードは任意のディレクトリ・ファイルに記載してください。
### APIキーの設定
先ほど取得したCohereとTavilyのAPIキーをそれぞれ設定します。
```
import os
os.environ['COHERE_API_KEY'] = "<取得したCohere APIキー>"
os.environ['TAVILY_API_KEY'] = "<取得した自身のTavily APIキー>"
```

### LLMの設定
Langchainを使用して、CohereのLLMを呼び出します。
ちなみに、`temperature`については[こちら](https://www.promptingguide.ai/jp/introduction/settings)を参考にしてください。今回はデータアナリストに、より事実に基づいた回答をしてもらいたいので`temperature=0`にしました。
```
from langchain_cohere.chat_models import ChatCohere
chat = ChatCohere(model="command-r-plus", temperature=0)
```

### Web Searchの設定
Tavilyを使用して、テキストクエリに基づいた関連するドキュメントの[スニペット](https://japan.zdnet.com/glossary/exp/%E3%82%B9%E3%83%8B%E3%83%9A%E3%83%83%E3%83%88/?s=4#:~:text=%E3%82%B9%E3%83%8B%E3%83%9A%E3%83%83%E3%83%88%E3%81%A8%E3%81%AF&text=%E3%82%B9%E3%83%8B%E3%83%9A%E3%83%83%E3%83%88%E3%81%A8%E3%81%AF%E3%80%81%E4%B8%80%E8%88%AC%E7%9A%84,%E6%96%87%E3%81%AE%E3%81%93%E3%81%A8%E3%81%A7%E3%81%82%E3%82%8B%E3%80%82)を返却します。
```
from langchain_community.tools.tavily_search import TavilySearchResults
internet_search = TavilySearchResults()
internet_search.name = "internet_search"
internet_search.description = "Returns a list of relevant document snippets for a textual query retrieved from the internet."

from langchain_core.pydantic_v1 import BaseModel, Field
class TavilySearchInput(BaseModel):
    query: str = Field(description="Query to search the internet with")
internet_search.args_schema = TavilySearchInput
```

### Python Interpreterの設定
Pythonコードを実行するためのを設定しています。
```
from langchain.agents import Tool
from langchain_experimental.utilities import PythonREPL
python_repl = PythonREPL()
repl_tool = Tool(
    name="python_repl",
    description="Executes python code and returns the result. The code runs in a static sandbox without interactive mode, so print output or save output to a file.",
    func=python_repl.run,
)
repl_tool.name = "python_interpreter"

class ToolInput(BaseModel):
    code: str = Field(description="Python code to execute.")
repl_tool.args_schema = ToolInput
```

### AIデータアナリストエージェントの設定
エージェントを設定し、指定されたタスクを実行するようにしています。
```
from langchain.agents import AgentExecutor
from langchain_cohere.react_multi_hop.agent import create_cohere_react_agent
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_template("{input}")

agent = create_cohere_react_agent(
    llm=llm,
    tools=[internet_search, repl_tool],
    prompt=prompt,
)

agent_executor = AgentExecutor(agent=agent, tools=[internet_search, repl_tool], verbose=True)
```

### プロンプト記載
`"input": "<ここに好きなようにプロンプトを入力してください>"`
今回のプロンプトは「**2024年における米国の時価総額上位ハイテク企業3社の売上高成長率をプロットしてください。売上高成長率＝（当期の売上高-前期の売上高）／前期の売上高**」としました。
```
agent_executor.invoke({
    "input": "Create a plot of sales growth for the three largest high-tech companies in the U.S. by market capitalization in 2024 now. Sales growth rate = (current year sales - previous year sales)/previous year sales",
})
```

上記のコードを記載したファイルを実行してください。
ターミナルでファイルのあるディレクトリに移動して、`python <ファイル名>.py`で実行できます。

# 結果
以下の図がファイルと同じディレクトリに出力されました。
（たまに時間差で出力されたり出力されなかったり、、）

![sales_growth_rate.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3578596/ca3febc7-784d-2b69-faf2-f9852d32796b.png)


2024/8/11時点での米国の時価総額上位3社は以下の通りだったので合っていそうです。（[日本経済新聞のサイト](https://www.nikkei.com/marketdata/ranking-us/market-cap-high/)より）
![image.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3578596/e0a2ae40-9d4e-d1af-faee-666648c6602b.png)

企業の売上高成長率ですが、めんどくさいので実際に計算して確認していないです、ごめんなさい。。
（Appleの成長率がかなり怪しいので間違っていそう）

# 使用してみた感想
現在（2024/8/11）、OpenAIのGPT-4oは2023年12月までしかデータを学習していないので、同じプロンプトを投げると去年時点における米国の時価総額上位3社を選んでしまいます。その点では、リアルタイムでインターネット検索をしてくれる今回のAIエージェントは優位であると思います。ただChatGPTのようにレスポンスを起点として連続した会話ができない点だったり、信用性に欠けるので普段使いはできないですね。。

興味を持って下さりありがとうございました！
