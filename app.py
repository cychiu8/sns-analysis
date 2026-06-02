"""
Japan TEDx Instagram post analysis — Streamlit interactive dashboard

Usage:
    pip install streamlit pandas plotly
    streamlit run app.py

Data sources (place in the same folder as app.py):
    tedx_account_all_v2.csv  (account-level summary)
    tedx_posts_all_v2.csv    (post-level detail)
"""

import re
import collections
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="TEDx Instagram 分析", page_icon="📊", layout="wide")

TED_RED = "#EB0028"
HIGHLIGHT_ACC = "tedxhamamatsu"
PALETTE = ["#EB0028", "#F46A6A", "#C9A227", "#3A7CA5", "#6B8E23", "#9B59B6", "#888888"]
WD_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WD_JP = {"Mon": "月曜日", "Tue": "火曜日", "Wed": "水曜日", "Thu": "木曜日",
         "Fri": "金曜日", "Sat": "土曜日", "Sun": "日曜日"}
TYPE_JP = {"Reel": "リール", "GraphSidecar": "カルーセル", "photo": "写真"}
BAND_ORDER = ["朝（05-10）", "昼（11-13）", "午後（14-17）", "夜（18-21）", "深夜（22-04）"]
THEME_ORDER = ["応募・募集", "スピーカー紹介", "理念・メッセージ", "舞台裏・チーム", "イベント回顧", "その他"]

RULES = {
    "応募・募集": {"スタッフ募集": 5, "ボランティア": 4, "オーディション": 5, "公募": 5,
              "応募": 4, "募集": 4, "エントリー": 4, "参加申": 4, "申し込み": 2, "申込": 2,
              "チケット": 2, "ticket": 2, "register": 3, "お申し込み": 2, "登壇者公募": 5,
              "スピーカー募集": 5, "参加者募集": 5, "受付": 2, "購入": 2, "先着": 3,
              "抽選": 3, "apply": 3, "recruit": 4, "説明会": 3},
    "スピーカー紹介": {"スピーカー紹介": 6, "登壇者紹介": 6, "speaker reveal": 6, "スピーカー公開": 5,
              "トーク紹介": 5, "登壇": 3, "speaker": 3, "スピーカー": 2, "プロフィール": 2,
              "語っていただ": 3, "トークを": 2, "本イベントにて": 2, "reveal": 3,
              "紹介します": 1, "speakers": 3},
    "イベント回顧": {"お疲れ様": 5, "ありがとうございました": 4, "開催しました": 5, "開催されました": 5,
              "無事": 3, "終了": 3, "レポート": 4, "振り返": 5, "盛況": 4, "recap": 5,
              "報告": 3, "アーカイブ": 4, "youtu.be": 3, "youtube": 2, "動画": 2, "ご来場": 3,
              "ご参加いただ": 3, "開催いたしました": 5, "was held": 4, "were held": 4,
              "一ヶ月": 2, "1ヶ月": 2, "当日は": 3, "アフターパーティー開始": 4},
    "舞台裏・チーム": {"インタビュー": 5, "実行委員会": 4, "メンバー紹介": 5, "舞台裏": 6, "behind": 5,
              "幕後": 6, "準備を進め": 4, "パートナー": 4, "partner": 4, "協賛": 4,
              "サポーター": 5, "supporter": 5, "キービジュアル": 4, "リハーサル": 5, "設営": 5,
              "打ち合わせ": 5, "スタッフの": 3, "メンバー": 2, "フード紹介": 5, "in-kind": 4,
              "会場紹介": 4, "チーム": 2, "後援": 4, "ご支援": 2, "紹介です": 3, "協力": 2,
              "裏側": 5, "密着": 4, "ブース紹介": 5, "出展": 3},
    "理念・メッセージ": {"ideas worth spreading": 6, "ideas change everything": 6, "理念": 5,
              "purpose": 5, "価値あるアイデア": 5, "一期一会": 4, "spread": 3, "メッセージ": 3,
              "問いかけ": 4, "テーマ": 3, "theme": 3, "想い": 3, "世界を変える": 4, "信念": 4,
              "広げる団体": 4, "アイデア": 1, "idea": 1, "spark": 3, "break the norm": 4,
              "mission": 4, "vision": 3, "セッション": 2, "session": 2, "視点": 2,
              "世界を動かす": 4, "開催決定": 2},
}
PRIORITY = ["応募・募集", "スピーカー紹介", "イベント回顧", "舞台裏・チーム", "理念・メッセージ"]
MULTI_THRESHOLD = 3

EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U00002700-\U000027BF\U00002190-\U000021FF]",
    flags=re.UNICODE)
KATA_RE = re.compile(r"[ァ-ヴー]{2,}")
KANJI_RE = re.compile(r"[一-龥]{2,4}")
ASCII_RE = re.compile(r"[A-Za-z]{3,}")

KW_STOP = set("""
tedx ted tedtalks tedxkobe tedxkyoto tedxhamamatsu tedxutokyo tedxkeiou tedxawaji
tedxwasedau ideasworthspreading tedcircles tedxtalks https http com www jp the and
for you our with this will are has have was were that from your they not但 event events
peatix イベント この より ため こと そして また ます です ました ください という
""".split())


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def hour_to_band(h):
    if 5 <= h <= 10:
        return "朝（05-10）"
    if 11 <= h <= 13:
        return "昼（11-13）"
    if 14 <= h <= 17:
        return "午後（14-17）"
    if 18 <= h <= 21:
        return "夜（18-21）"
    return "深夜（22-04）"


def caption_scores(text):
    low = text.lower()
    return {c: sum(w for k, w in kw.items() if k in low) for c, kw in RULES.items()}


def assign_themes(text):
    if not isinstance(text, str) or not text.strip():
        return ["その他"], "その他"
    s = caption_scores(text)
    mx = max(s.values())
    if mx == 0:
        return ["その他"], "その他"
    primary = [c for c in PRIORITY if s.get(c, 0) == mx][0]
    multi = [c for c in PRIORITY if s.get(c, 0) >= MULTI_THRESHOLD]
    if not multi:
        multi = [primary]
    return multi, primary


def extract_emojis(series):
    cnt = collections.Counter()
    for c in series.dropna():
        for e in EMOJI_RE.findall(c):
            cnt[e] += 1
    return cnt


def extract_keywords(series):
    cnt = collections.Counter()
    for c in series.dropna():
        toks = KATA_RE.findall(c) + KANJI_RE.findall(c) + [a.lower() for a in ASCII_RE.findall(c)]
        for t in toks:
            if t.lower() in KW_STOP or len(t) < 2:
                continue
            cnt[t] += 1
    return cnt


def acc_color_map(acc_list):
    """Return color_discrete_map highlighting tedxhamamatsu in red, others in grey."""
    return {a: TED_RED if a == HIGHLIGHT_ACC else "#BBBBBB" for a in acc_list}


def highlight_row(styler):
    """Apply a red background to the tedxhamamatsu row in a dataframe."""
    return styler.apply(
        lambda row: [
            "background-color: #fff0f0; font-weight: bold" if row.name == HIGHLIGHT_ACC else ""
            for _ in row
        ],
        axis=1,
    )


# ----------------------------------------------------------------------
# Data loading and preprocessing
# ----------------------------------------------------------------------
@st.cache_data
def load_data():
    acc = pd.read_csv("data/tedx_account_all_v2.csv")
    posts_raw = pd.read_csv("data/tedx_posts_all_v2.csv")
    df = posts_raw.copy()
    df["caption"] = df["caption"].fillna("")
    df["dt"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["year"] = df["dt"].dt.year
    df["band"] = df["hour"].apply(hour_to_band)
    df["type_jp"] = df["type"].map(TYPE_JP).fillna(df["type"])
    res = df["caption"].apply(assign_themes)
    df["themes"] = res.apply(lambda x: x[0])
    df["primary"] = res.apply(lambda x: x[1])
    return acc, df


def overview_table(acc):
    return acc[acc.block == "overview"].pivot_table(
        index="account", columns="metric", values="value", aggfunc="first")


# ----------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------
try:
    acc_df, posts_all = load_data()
except FileNotFoundError as e:
    st.title("📊 日本 TEDx Instagram 投稿分析")
    st.error(f"CSVファイルが見つかりません: {e}\n\n"
             "`tedx_account_all_v2.csv` と `tedx_posts_all_v2.csv` を app.py と同じフォルダに配置してください。")
    st.stop()

ov_all = overview_table(acc_df)

# ----------------------------------------------------------------------
# Sidebar — filters only
# ----------------------------------------------------------------------
st.sidebar.header("⚙️ 絞り込み")
st.sidebar.markdown(
    f"<div style='background:#fff0f0;border-left:4px solid {TED_RED};"
    f"padding:8px 10px;border-radius:4px;margin-bottom:8px'>",
    f"</div>",
    unsafe_allow_html=True)

accounts = sorted(posts_all["account"].unique())
sel_acc = st.sidebar.multiselect("アカウント", accounts, default=accounts)
types = list(posts_all["type"].unique())
sel_type = st.sidebar.multiselect("投稿タイプ", types, default=types,
                                  format_func=lambda t: TYPE_JP.get(t, t))
sel_theme = st.sidebar.multiselect("コンテンツテーマ", THEME_ORDER, default=THEME_ORDER)
min_d, max_d = posts_all["dt"].min().date(), posts_all["dt"].max().date()
date_range = st.sidebar.date_input("期間", (min_d, max_d), min_value=min_d, max_value=max_d)

# Apply filters
df = posts_all[posts_all["account"].isin(sel_acc) & posts_all["type"].isin(sel_type)].copy()
df = df[df["themes"].apply(lambda L: bool(set(L) & set(sel_theme)))]
if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    d0, d1 = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
    df = df[(df["dt"] >= d0) & (df["dt"] < d1)]

if df.empty:
    st.title("📊 日本 TEDx Instagram 投稿分析")
    st.error("現在の絞り込み条件に該当する投稿がありません。条件を緩めてください。")
    st.stop()

expl = df.explode("themes").rename(columns={"themes": "theme"})

# ----------------------------------------------------------------------
# Page title
# ----------------------------------------------------------------------
st.markdown(
    f"<h1 style='color:{TED_RED};margin-bottom:0'>📊 日本 TEDx Instagram 投稿分析</h1>"
    f"<p style='color:#666;margin-top:4px'>インタラクティブダッシュボード ｜ "
    f"絞り込み後 {len(df):,} 件の投稿</p>",
    unsafe_allow_html=True)

# ----------------------------------------------------------------------
# KPI cards
# ----------------------------------------------------------------------
ov_sel = ov_all.loc[[a for a in sel_acc if a in ov_all.index]]
tot_followers = int(ov_sel["followers"].sum()) if "followers" in ov_sel else 0
best_er_acc = ov_sel["avg_engagement_rate"].idxmax() if len(ov_sel) else "—"
top_theme = expl["theme"].value_counts().idxmax()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("対象アカウント数", f"{df['account'].nunique()} 個")
c2.metric("投稿数", f"{len(df):,}")
c3.metric("合計フォロワー数", f"{tot_followers:,}")
c4.metric("平均エンゲージメント率", f"{df['engagement_rate'].mean():.2f}%")
c5.metric("最多テーマ", top_theme)

st.divider()

# ----------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 アカウント概要", "🎬 投稿タイプ", "🕒 投稿タイミング",
    "🎯 コンテンツテーマ", "#️⃣ ハッシュタグ", "🔥 人気投稿 & 明細"
])

# ===== Tab 1: Account overview =====
with tab1:
    st.subheader("アカウント比較概要")
    g = (df.groupby("account")
           .agg(投稿数=("shortcode", "count"),
                平均いいね数=("likes", "mean"),
                平均コメント数=("comments", "mean"),
                平均エンゲージメント=("engagement", "mean"),
                平均エンゲージメント率=("engagement_rate", "mean"))
           .round(2))
    g["フォロワー数"] = ov_all["followers"].reindex(g.index).astype("Int64")
    g["総投稿数"] = ov_all["total_posts"].reindex(g.index).astype("Int64")
    g = g[["フォロワー数", "総投稿数", "投稿数", "平均いいね数", "平均コメント数",
           "平均エンゲージメント", "平均エンゲージメント率"]]
    g = g.sort_values("平均エンゲージメント率", ascending=False)
    st.dataframe(highlight_row(g.style), use_container_width=True)

    colA, colB = st.columns(2)
    g_r = g.reset_index()
    with colA:
        fig = px.bar(g_r, x="account", y="フォロワー数", title="フォロワー数",
                     color="account", color_discrete_map=acc_color_map(g_r["account"]))
        fig.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        fig = px.bar(g_r, x="account", y="平均エンゲージメント率",
                     title="平均エンゲージメント率 (%)",
                     color="account", color_discrete_map=acc_color_map(g_r["account"]))
        fig.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig, use_container_width=True)

    st.info("インサイト：フォロワー規模とエンゲージメント率は逆相関になりやすいです。"
            "大規模アカウントはリーチは広いですが粘着度は低く、小規模アカウントはより活発なエンゲージメントが見られます。")

# ===== Tab 2: Post type performance =====
with tab2:
    st.subheader("投稿タイプ別パフォーマンス")
    pt = (df.groupby("type_jp")
            .agg(投稿数=("shortcode", "count"),
                 平均エンゲージメント率=("engagement_rate", "mean"),
                 平均エンゲージメント=("engagement", "mean"))
            .round(2)
            .sort_values("平均エンゲージメント率", ascending=False))
    pt["割合(%)"] = (pt["投稿数"] / pt["投稿数"].sum() * 100).round(1)

    colA, colB = st.columns(2)
    with colA:
        st.dataframe(pt[["投稿数", "割合(%)", "平均エンゲージメント率", "平均エンゲージメント"]],
                     use_container_width=True)
        fig = px.pie(pt.reset_index(), names="type_jp", values="投稿数",
                     title="投稿タイプ別割合", color_discrete_sequence=PALETTE, hole=0.4)
        fig.update_layout(height=340)
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        fig = px.bar(pt.reset_index(), x="type_jp", y="平均エンゲージメント率",
                     title="タイプ別平均エンゲージメント率 (%)", color="type_jp",
                     color_discrete_sequence=PALETTE)
        fig.update_layout(showlegend=False, height=340)
        st.plotly_chart(fig, use_container_width=True)

        reel = (df.groupby("account")["type"]
                  .apply(lambda s: (s == "Reel").mean() * 100).round(1)
                  .rename("リール採用率(%)").reset_index())
        fig2 = px.bar(reel, x="account", y="リール採用率(%)",
                      title="アカウント別 リール採用率 (%)",
                      color="account", color_discrete_map=acc_color_map(reel["account"]))
        fig2.update_layout(showlegend=False, height=340)
        st.plotly_chart(fig2, use_container_width=True)

# ===== Tab 3: Posting timing =====
with tab3:
    st.subheader("投稿タイミング分析")
    colA, colB = st.columns(2)
    with colA:
        w = (df.groupby("weekday")["engagement_rate"].mean()
               .reindex(WD_ORDER).round(2).reset_index())
        w["曜日"] = w["weekday"].map(WD_JP)
        fig = px.line(w, x="曜日", y="engagement_rate", markers=True,
                      title="曜日別 平均エンゲージメント率 (%)",
                      color_discrete_sequence=[TED_RED])
        fig.update_layout(height=380, yaxis_title="エンゲージメント率(%)")
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        b = (df.groupby("band")["engagement_rate"].mean()
               .reindex(BAND_ORDER).round(2).reset_index())
        fig = px.bar(b, x="band", y="engagement_rate",
                     title="時間帯別 平均エンゲージメント率 (%)", color="band",
                     color_discrete_sequence=PALETTE)
        fig.update_layout(showlegend=False, height=380, yaxis_title="エンゲージメント率(%)",
                          xaxis_title="時間帯")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**曜日 × 時間帯 ヒートマップ（平均エンゲージメント率）**")
    pivot = (df.pivot_table(index="band", columns="weekday",
                            values="engagement_rate", aggfunc="mean")
               .reindex(index=BAND_ORDER, columns=WD_ORDER))
    pivot.columns = [WD_JP[c] for c in pivot.columns]
    fig = px.imshow(pivot, text_auto=".1f", aspect="auto",
                    color_continuous_scale="Reds",
                    labels=dict(color="エンゲージメント率(%)"))
    fig.update_layout(height=360)
    st.plotly_chart(fig, use_container_width=True)

# ===== Tab 4: Content themes =====
with tab4:
    st.subheader("テーマ分布（複数ラベル）")
    st.caption("1件の投稿が複数のテーマに属することがあるため、割合の合計は100%を超えます。")
    mem = expl["theme"].value_counts().reindex(THEME_ORDER).fillna(0).astype(int)
    memdf = pd.DataFrame({"テーマ": mem.index, "投稿数": mem.values,
                          "全投稿に占める割合(%)": (mem.values / len(df) * 100).round(1)})
    colA, colB = st.columns([1.2, 1])
    with colA:
        fig = (px.bar(memdf, x="投稿数", y="テーマ", orientation="h", text="投稿数",
                      title="テーマ別投稿数", color_discrete_sequence=[TED_RED])
               .update_layout(showlegend=False, height=360,
                               yaxis={"categoryorder": "total ascending"}))
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        er_theme = expl.groupby("theme")["engagement_rate"].mean().reindex(THEME_ORDER).round(2).reset_index()
        fig = (px.bar(er_theme, x="engagement_rate", y="theme", orientation="h",
                      title="テーマ別平均エンゲージメント率(%)", color_discrete_sequence=["#C9A227"])
               .update_layout(showlegend=False, height=360,
                               yaxis={"categoryorder": "total ascending"},
                               xaxis_title="エンゲージメント率(%)", yaxis_title=""))
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("テーマ別 キーワード / Emoji クラウドとトップ投稿")
    pick = st.selectbox("テーマを選択", THEME_ORDER, index=0)
    sub = df[df["themes"].apply(lambda L: pick in L)]
    st.caption(f"「{pick}」{len(sub):,} 件　｜　平均エンゲージメント率 "
               f"{sub['engagement_rate'].mean():.2f}%　｜　平均いいね数 {sub['likes'].mean():.0f}")

    k1, k2 = st.columns(2)
    kw = extract_keywords(sub["caption"]).most_common(30)
    if kw:
        kdf = pd.DataFrame(kw, columns=["キーワード", "件数"])
        fig = px.treemap(kdf, path=["キーワード"], values="件数",
                         title=f"「{pick}」キーワードクラウド",
                         color="件数", color_continuous_scale="Reds")
        fig.update_layout(height=400, margin=dict(t=40, l=0, r=0, b=0))
        k1.plotly_chart(fig, use_container_width=True)
    else:
        k1.info("キーワードが十分にありません。")

    emo = extract_emojis(sub["caption"]).most_common(20)
    if emo:
        edf = pd.DataFrame(emo, columns=["emoji", "件数"])
        fig = px.treemap(edf, path=["emoji"], values="件数",
                         title=f"「{pick}」Emoji クラウド",
                         color="件数", color_continuous_scale="Oranges")
        fig.update_layout(height=400, margin=dict(t=40, l=0, r=0, b=0),
                          uniformtext=dict(minsize=18))
        fig.update_traces(textfont_size=26)
        k2.plotly_chart(fig, use_container_width=True)
    else:
        k2.info("このテーマではEmojiの使用が少ないです。")

    st.markdown(f"**「{pick}」トップ投稿（エンゲージメント Top 5）**")
    best = sub.sort_values("engagement", ascending=False).head(5).copy()
    best["日付"] = best["dt"].dt.strftime("%Y-%m-%d")
    best["抜粋"] = best["caption"].str.replace("\n", " ", regex=False).str.slice(0, 90)
    show = best[["account", "日付", "type_jp", "likes", "comments", "engagement",
                 "engagement_rate", "抜粋", "url"]].rename(
        columns={"account": "アカウント", "type_jp": "タイプ", "likes": "いいね", "comments": "コメント",
                 "engagement": "エンゲージメント", "engagement_rate": "エンゲージメント率(%)", "url": "リンク"})
    st.dataframe(show, use_container_width=True, hide_index=True,
                 column_config={"リンク": st.column_config.LinkColumn("リンク")})

# ===== Tab 5: Hashtags =====
with tab5:
    st.subheader("ハッシュタグ分析")
    cnt = collections.Counter()
    for s in df["primary_hashtags"].dropna():
        for tag in str(s).split():
            cnt[tag.lower()] += 1
    topn = st.slider("表示するタグ数（上位 N 件）", 5, 30, 20)
    htags = pd.DataFrame(cnt.most_common(topn), columns=["タグ", "件数"])
    htags["タグ"] = "#" + htags["タグ"]
    if htags.empty:
        st.info("絞り込み後にタグデータがありません。")
    else:
        fig = px.bar(htags.sort_values("件数"), x="件数", y="タグ",
                     orientation="h", title=f"Top {topn} ハッシュタグ",
                     color_discrete_sequence=[TED_RED])
        fig.update_layout(height=max(380, topn * 22), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)
    c1.metric("タグ数 vs エンゲージメント率 相関係数",
              f"{df['hashtag_count'].corr(df['engagement_rate']):+.3f}")
    c2.metric("文字数 vs エンゲージメント率 相関係数",
              f"{df['words'].corr(df['engagement_rate']):+.3f}")
    st.caption("どちらも弱い相関です。タグ数や文字数を増やすだけではエンゲージメント向上は限定的であり、"
               "コンテンツの質とタイミングが重要です。")

# ===== Tab 6: Top posts and raw detail =====
with tab6:
    st.subheader("人気投稿 TOP 20（エンゲージメント順）")
    top = df.sort_values("engagement", ascending=False).head(20).copy()
    top["日付"] = top["dt"].dt.strftime("%Y-%m-%d")
    top["テーマ"] = top["themes"].apply(lambda L: "／".join(L))
    show = top[["account", "日付", "テーマ", "type_jp", "likes", "comments",
                "engagement", "engagement_rate", "url"]].rename(
        columns={"account": "アカウント", "type_jp": "タイプ", "likes": "いいね", "comments": "コメント",
                 "engagement": "エンゲージメント", "engagement_rate": "エンゲージメント率(%)", "url": "リンク"})
    st.dataframe(show, use_container_width=True, hide_index=True,
                 column_config={"リンク": st.column_config.LinkColumn("リンク")})

    st.divider()
    st.subheader("投稿明細データ（ダウンロード可）")
    out = df.copy()
    out["themes"] = out["themes"].apply(lambda L: "／".join(L))
    cols = ["account", "datetime", "weekday", "hour", "themes", "primary", "type",
            "likes", "comments", "engagement", "engagement_rate", "words",
            "hashtag_count", "primary_hashtags", "followers", "url"]
    st.dataframe(out[cols].sort_values(["account", "datetime"]),
                 use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ 絞り込み後のデータをダウンロード (CSV)",
        out[cols].to_csv(index=False).encode("utf-8-sig"),
        file_name="tedx_filtered.csv", mime="text/csv")

st.divider()
st.caption("データソース：Instagram 投稿収集。エンゲージメント率 = （いいね + コメント）/ フォロワー数。"
           "テーマはルールベースのキーワード複数ラベル分類（スコア ≥ 3 で分類）。"
           "各アカウントの投稿数は直近のサンプル（最大 200 件）です。")
