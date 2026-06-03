"""
Japan TEDx Instagram post analysis — Streamlit interactive dashboard

Usage:
    pip install streamlit pandas plotly
    streamlit run app.py

Data sources (place in the same folder as app.py):
    tedx_account_all.csv  (account-level summary)
    tedx_posts_all.csv    (post-level detail)
"""

import re
import hashlib
import json
import collections
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="TEDx Instagram 分析", page_icon="📊", layout="wide")

TED_RED = "#c22d0e"
HIGHLIGHT_ACC = "tedxhamamatsu"
PALETTE = ["#c22d0e", "#772315", "#b77e74", "#ecbca4", "#dac1bd", "#492822", "#888888"]
TYPE_PALETTE = {"リール": "#c22d0e", "カルーセル": "#b77e74", "写真": "#dac1bd"}
WD_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WD_JP = {"Mon": "月曜日", "Tue": "火曜日", "Wed": "水曜日", "Thu": "木曜日",
         "Fri": "金曜日", "Sat": "土曜日", "Sun": "日曜日"}
TYPE_JP = {"Reel": "リール", "GraphSidecar": "カルーセル", "photo": "写真"}
BAND_ORDER = ["朝（05-10）", "昼（11-13）", "午後（14-17）", "夜（18-21）", "深夜（22-04）"]
THEME_ORDER = ["スタッフ・メンバー募集", "チケット・参加申込", "スピーカー紹介", "理念・メッセージ", "舞台裏・チーム", "イベント回顧", "その他"]

RULES = {
    "スタッフ・メンバー募集": {"スタッフ募集": 5, "ボランティア": 4, "オーディション": 5, "公募": 5,
              "応募": 4, "募集": 4, "エントリー": 4, "登壇者公募": 5,
              "スピーカー募集": 5, "参加者募集": 5, "apply": 3, "recruit": 4, "説明会": 3},
    "チケット・参加申込": {"チケット": 4, "ticket": 4, "register": 3, "お申し込み": 3,
              "申し込み": 3, "申込": 3, "参加申": 3, "受付": 3, "購入": 3,
              "先着": 4, "抽選": 4},
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
PRIORITY = ["スタッフ・メンバー募集", "チケット・参加申込", "スピーカー紹介", "イベント回顧", "舞台裏・チーム", "理念・メッセージ"]
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
_RULES_HASH = hashlib.md5(
    json.dumps(RULES, sort_keys=True, ensure_ascii=False).encode()
).hexdigest()[:8]

@st.cache_data
def load_data(rules_hash: str = _RULES_HASH):  # noqa: ARG001
    acc = pd.read_csv("data/tedx_account_all.csv")
    posts_raw = pd.read_csv("data/tedx_posts_all.csv")
    df = posts_raw.copy()
    df["caption"] = df["caption"].fillna("")
    df["dt"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df[df["dt"].dt.year >= 2023].copy()
    df["year"] = df["dt"].dt.year
    for col in ["video_view_count", "video_play_count", "video_duration"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
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
             "`tedx_account_all.csv` と `tedx_posts_all.csv` を app.py と同じフォルダに配置してください。")
    st.stop()

ov_all = overview_table(acc_df)

# ----------------------------------------------------------------------
# Sidebar — filters only
# ----------------------------------------------------------------------
st.sidebar.header("⚙️ 絞り込み")

if "filter_v" not in st.session_state:
    st.session_state.filter_v = 0

if st.sidebar.button("🔄 フィルターをリセット", use_container_width=True):
    st.session_state.filter_v += 1

_v = st.session_state.filter_v

with st.sidebar.expander("📋 更新履歴", expanded=False):
    st.caption(
        "**最新版** 2025-06-03  \n"
        "- 分析対象を2023年以降に限定  \n"
        "- リール動画指標追加（視聴転換率・尺別分析）"
    )

accounts = sorted(posts_all["account"].unique())
sel_acc = st.sidebar.multiselect("アカウント", accounts, default=accounts, key=f"sel_acc_{_v}")
types = list(posts_all["type"].unique())
sel_type = st.sidebar.multiselect("投稿タイプ", types, default=types,
                                  format_func=lambda t: TYPE_JP.get(t, t), key=f"sel_type_{_v}")
sel_theme = st.sidebar.multiselect("コンテンツテーマ", THEME_ORDER, default=THEME_ORDER, key=f"sel_theme_{_v}")
min_d, max_d = posts_all["dt"].min().date(), posts_all["dt"].max().date()
date_range = st.sidebar.date_input("期間", (min_d, max_d), min_value=min_d, max_value=max_d, key=f"date_range_{_v}")

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
top_followers_acc = ov_sel["followers"].idxmax() if "followers" in ov_sel.columns and not ov_sel["followers"].isna().all() else "—"
top_followers_val = int(ov_sel.loc[top_followers_acc, "followers"]) if top_followers_acc != "—" else 0
_er_by_acc = df.groupby("account")["engagement_rate"].mean()
best_er_acc = _er_by_acc.idxmax() if len(_er_by_acc) else "—"
best_er_val = round(float(_er_by_acc.loc[best_er_acc]), 2) if best_er_acc != "—" else 0.0
top_theme = expl["theme"].value_counts().idxmax()
acc_list_str = "、".join(sorted(df["account"].unique()))
_expl_no_other = expl[expl["theme"] != "その他"]
best_er_theme = _expl_no_other.groupby("theme")["engagement_rate"].mean().idxmax() if len(_expl_no_other) > 0 else "—"
best_er_theme_val = round(_expl_no_other.groupby("theme")["engagement_rate"].mean().max(), 2) if len(_expl_no_other) > 0 else 0.0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("対象アカウント数", f"{df['account'].nunique()} 個", help=acc_list_str)
c2.markdown(
    f"<div style='font-size:0.875rem;color:#555'>最多フォロワーアカウント</div>"
    f"<div style='font-size:1.5rem;font-weight:700;line-height:1.3'>{top_followers_acc}</div>"
    f"<div style='font-size:0.875rem;color:#555'>{top_followers_val:,} フォロワー</div>",
    unsafe_allow_html=True,
)
c3.metric("平均エンゲージメント率", f"{df['engagement_rate'].mean():.2f}%")
c4.markdown(
    f"<div style='font-size:0.875rem;color:#555'>平均エンゲージメント率最高アカウント</div>"
    f"<div style='font-size:1.5rem;font-weight:700;line-height:1.3'>{best_er_acc}</div>"
    f"<div style='font-size:0.875rem;color:#555'>{best_er_val:.2f}%</div>",
    unsafe_allow_html=True,
)
c5.markdown(
    f"<div style='font-size:0.875rem;color:#555'>最多テーマ</div>"
    f"<div style='font-size:1.5rem;font-weight:700;line-height:1.3;word-break:break-all'>{top_theme}</div>",
    unsafe_allow_html=True,
)
c6.markdown(
    f"<div style='font-size:0.875rem;color:#555'>平均エンゲージメント率最高テーマ</div>"
    f"<div style='font-size:1.5rem;font-weight:700;line-height:1.3;word-break:break-all'>{best_er_theme}</div>"
    f"<div style='font-size:0.875rem;color:#555'>{best_er_theme_val:.2f}%</div>",
    unsafe_allow_html=True,
)

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
    fmt = {c: "{:.2f}" for c in ["平均いいね数", "平均コメント数", "平均エンゲージメント", "平均エンゲージメント率"]}
    st.dataframe(highlight_row(g.style).format(fmt), use_container_width=True)

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

    _top2_followers = g.dropna(subset=["フォロワー数"]).sort_values("フォロワー数", ascending=False).head(2)
    _top2_names = "／".join(_top2_followers.index.tolist())
    _top2_er = _top2_followers["平均エンゲージメント率"].mean()
    _best_er_row_g = g["平均エンゲージメント率"].idxmax()
    _best_er_val = g.loc[_best_er_row_g, "平均エンゲージメント率"]
    _best_followers = int(g.loc[_best_er_row_g, "フォロワー数"]) if pd.notna(g.loc[_best_er_row_g, "フォロワー数"]) else "—"
    st.info(
        f"**インサイト①** フォロワー規模とエンゲージメント率は必ずしも比例しません。"
        f"フォロワー最多の **{_top2_names}** の平均エンゲージメント率は **{_top2_er:.2f}%** 程度にとどまる一方、"
        f"フォロワーが少ない **{_best_er_row_g}**（{_best_followers:,} 人）は **{_best_er_val:.2f}%** と全体最高を記録しており、"
        "受け手との粘着度が際立って高いことを示しています。"
    )

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

    # Row 1: ER bar | pie
    colA, colB = st.columns(2)
    with colA:
        fig = px.bar(pt.reset_index(), x="type_jp", y="平均エンゲージメント率",
                     title="タイプ別平均エンゲージメント率 (%)", color="type_jp",
                     color_discrete_map=TYPE_PALETTE)
        fig.update_layout(showlegend=False, height=360)
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        fig = px.pie(pt.reset_index(), names="type_jp", values="投稿数",
                     title="投稿タイプ別割合", color="type_jp",
                     color_discrete_map=TYPE_PALETTE, hole=0.4)
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)

    # Row 2: table | リール採用率
    colC, colD = st.columns(2)
    with colC:
        st.markdown("**投稿タイプ別サマリー**")
        st.dataframe(pt[["投稿数", "割合(%)", "平均エンゲージメント率", "平均エンゲージメント"]],
                     use_container_width=True)
    with colD:
        reel = (df.groupby("account")["type"]
                  .apply(lambda s: (s == "Reel").mean() * 100).round(1)
                  .rename("リール採用率(%)").reset_index())
        fig2 = px.bar(reel, x="account", y="リール採用率(%)",
                      title="アカウント別 リール採用率 (%)",
                      color="account", color_discrete_map=acc_color_map(reel["account"]))
        fig2.update_layout(showlegend=False, height=320)
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("テーマ × 投稿タイプ 別 平均エンゲージメント率（%）")
    theme_type = (
        df.explode("themes")
        .groupby(["themes", "type_jp"])["engagement_rate"]
        .mean()
        .round(2)
        .reset_index()
    )
    theme_type = theme_type[theme_type["themes"].isin(THEME_ORDER)]
    fig_tt = px.bar(
        theme_type,
        x="themes", y="engagement_rate", color="type_jp",
        barmode="group",
        text="engagement_rate",
        title="テーマ × 投稿タイプ 別 平均エンゲージメント率 (%)",
        category_orders={"themes": THEME_ORDER, "type_jp": ["リール", "カルーセル", "写真"]},
        color_discrete_map=TYPE_PALETTE,
        labels={"themes": "テーマ", "engagement_rate": "エンゲージメント率(%)", "type_jp": "投稿タイプ"},
    )
    fig_tt.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig_tt.update_layout(height=420, yaxis_title="エンゲージメント率(%)", xaxis_title="")
    st.plotly_chart(fig_tt, use_container_width=True)

    def _tt(theme, typ):
        r = theme_type[(theme_type["themes"] == theme) & (theme_type["type_jp"] == typ)]["engagement_rate"]
        return r.values[0] if len(r) > 0 else None

    _r_riron = _tt("理念・メッセージ", "リール")
    _p_riron = _tt("理念・メッセージ", "写真")
    _r_ura   = _tt("舞台裏・チーム",  "リール")
    _p_ura   = _tt("舞台裏・チーム",  "写真")
    _ratio   = f"{_r_ura / _p_ura:.1f}" if (_r_ura and _p_ura and _p_ura > 0) else "—"
    _fmt = lambda v: f"{v:.2f}" if v is not None else "—"
    st.info(
        f"**インサイト** Reel はすべてのテーマで平均エンゲージメント率を大幅に引き上げます。"
        f"例：理念・メッセージ Reel **{_fmt(_r_riron)}%** vs 単体写真 **{_fmt(_p_riron)}%**、"
        f"舞台裏・チーム Reel **{_fmt(_r_ura)}%** vs 単体写真 **{_fmt(_p_ura)}%**（約 {_ratio} 倍）。"
        "既存テーマを Reel 形式に切り替えることが、最も即効性の高い平均エンゲージメント率改善策です。"
    )

    st.divider()
    st.subheader("🎬 動画指標分析（リール限定）")
    st.caption("視聴転換率 ＝ （いいね＋コメント）÷ 再生回数 × 100。"
               "動画を見た人のうち何%が実際に反応したかを示す指標で、数値が高いほど視聴者の心を動かすコンテンツであることを意味します。")
    vdf = df[(df["type"] == "Reel") & df["video_view_count"].notna()].copy()
    vdf = vdf[vdf["video_view_count"] > 0]

    if vdf.empty:
        st.info("現在の絞り込み条件に該当するリール投稿のデータがありません。")
    else:
        vdf["view_eng_rate"] = vdf["engagement"] / vdf["video_view_count"] * 100

        ver = vdf.groupby("account")["view_eng_rate"].mean().round(2).reset_index()
        fig_ver = px.bar(ver, x="account", y="view_eng_rate",
                         title="アカウント別 視聴転換率（%）",
                         color="account", color_discrete_map=acc_color_map(ver["account"]))
        fig_ver.update_layout(showlegend=False, height=360, yaxis_title="転換率(%)")
        st.plotly_chart(fig_ver, use_container_width=True)

        _best_ver = ver.loc[ver["view_eng_rate"].idxmax()]
        _avg_ver = round(ver["view_eng_rate"].mean(), 2)
        st.info(
            f"**視聴転換率** 全体平均 {_avg_ver}%。"
            f"最高は **{_best_ver['account']}**（{_best_ver['view_eng_rate']:.2f}%）で、視聴者をいいね・コメントに転換する力が最も強い。"
        )

        theme_ver = (
            vdf.explode("themes")
            .groupby("themes")["view_eng_rate"]
            .agg(転換率=("mean"), 件数=("count"))
            .round(2)
            .reset_index()
        )
        theme_ver = theme_ver[theme_ver["themes"].isin(THEME_ORDER)]
        theme_ver["ラベル"] = theme_ver.apply(
            lambda r: f"{r['転換率']:.2f}%（{r['件数']}件）", axis=1)
        fig_tver = px.bar(
            theme_ver.sort_values("転換率", ascending=False),
            x="転換率", y="themes", orientation="h",
            text="ラベル",
            title="テーマ別 視聴転換率（リールのみ）",
            color_discrete_sequence=["#b77e74"],
            labels={"themes": "テーマ", "転換率": "転換率(%)"},
            category_orders={"themes": theme_ver.sort_values("転換率", ascending=False)["themes"].tolist()},
        )
        fig_tver.update_traces(textposition="inside", insidetextanchor="middle")
        fig_tver.update_layout(showlegend=False, height=360, xaxis_title="転換率(%)", yaxis_title="")
        st.plotly_chart(fig_tver, use_container_width=True)

        _best_theme_ver = theme_ver.loc[theme_ver["転換率"].idxmax()]
        _worst_theme_ver = theme_ver.loc[theme_ver["転換率"].idxmin()]
        st.info(
            f"**テーマ別転換率インサイト** リールの転換率が最も高いテーマは "
            f"**{_best_theme_ver['themes']}**（{_best_theme_ver['転換率']:.2f}%）、"
            f"最も低いのは **{_worst_theme_ver['themes']}**（{_worst_theme_ver['転換率']:.2f}%）。"
            "エンゲージメント率（いいね率）との差異に注目することで、視聴されても反応されにくいテーマを特定できます。"
        )

        dur_df = vdf.dropna(subset=["video_duration"]).copy()
        if not dur_df.empty:
            st.markdown("**リール尺別 パフォーマンス比較**")
            st.caption("短尺：〜15秒　｜　中尺：15〜30秒　｜　長尺：30秒〜")

            def dur_bucket(s):
                if s <= 15:
                    return "短尺（〜15秒）"
                if s <= 30:
                    return "中尺（15〜30秒）"
                return "長尺（30秒〜）"

            BUCKET_ORDER = ["短尺（〜15秒）", "中尺（15〜30秒）", "長尺（30秒〜）"]
            dur_df["尺"] = dur_df["video_duration"].apply(dur_bucket)
            dur_agg = (
                dur_df.groupby("尺")
                .agg(
                    平均エンゲージメント率=("engagement_rate", "mean"),
                    平均視聴転換率=("view_eng_rate", "mean"),
                    件数=("shortcode", "count"),
                )
                .round(2)
                .reindex(BUCKET_ORDER)
                .reset_index()
            )
            dur_agg["ラベル"] = dur_agg["件数"].apply(lambda n: f"{n}件")

            colA, colB = st.columns(2)
            with colA:
                fig_dur_er = px.bar(
                    dur_agg, x="尺", y="平均エンゲージメント率", text="ラベル",
                    title="リール尺別 平均エンゲージメント率（%）<br><sup>フォロワー全体に対する反応率</sup>",
                    color="尺", color_discrete_sequence=PALETTE,
                    category_orders={"尺": BUCKET_ORDER},
                )
                fig_dur_er.update_traces(textposition="outside")
                fig_dur_er.update_layout(showlegend=False, height=360, yaxis_title="エンゲージメント率(%)")
                st.plotly_chart(fig_dur_er, use_container_width=True)
            with colB:
                fig_dur_ver = px.bar(
                    dur_agg, x="尺", y="平均視聴転換率", text="ラベル",
                    title="リール尺別 視聴転換率（%）<br><sup>実際に動画を見た人に対する反応率</sup>",
                    color="尺", color_discrete_sequence=PALETTE,
                    category_orders={"尺": BUCKET_ORDER},
                )
                fig_dur_ver.update_traces(textposition="outside")
                fig_dur_ver.update_layout(showlegend=False, height=360, yaxis_title="転換率(%)")
                st.plotly_chart(fig_dur_ver, use_container_width=True)

            _best_er_bucket = dur_agg.loc[dur_agg["平均エンゲージメント率"].idxmax()]
            _best_ver_bucket = dur_agg.loc[dur_agg["平均視聴転換率"].idxmax()]
            st.info(
                f"**最適なリール尺** エンゲージメント率では **{_best_er_bucket['尺']}**"
                f"（{_best_er_bucket['平均エンゲージメント率']:.2f}%）、"
                f"視聴転換率では **{_best_ver_bucket['尺']}**"
                f"（{_best_ver_bucket['平均視聴転換率']:.2f}%）が最も高い結果となっています。"
                "長尺のエンゲージメント率が高い場合、関心の高いファン層が見ているため反応しやすい一方、"
                "アルゴリズムで広く配信された短尺は見知らぬユーザーにも届くため率が下がりやすい傾向があります。"
            )

            # テーマ × リール尺 別 視聴転換率（%）
            # サンプル数が少ないため非表示。データ量が増えたら with ブロックを外す。
            # with st.expander("テーマ × リール尺 別 視聴転換率（%）【参考：サンプル数少】", expanded=False):
            #     theme_dur = (
            #         dur_df.explode("themes")
            #         .groupby(["themes", "尺"])
            #         .agg(view_eng_rate=("view_eng_rate", "mean"), 件数=("shortcode", "count"))
            #         .round(2)
            #         .reset_index()
            #     )
            #     theme_dur = theme_dur[theme_dur["themes"].isin(THEME_ORDER)]
            #     theme_dur["ラベル"] = theme_dur.apply(
            #         lambda r: f"{r['view_eng_rate']:.2f}%\n({int(r['件数'])}件)", axis=1)
            #     fig_theme_dur = px.bar(
            #         theme_dur,
            #         x="themes", y="view_eng_rate", color="尺",
            #         barmode="group", text="ラベル",
            #         title="テーマ × リール尺 別 視聴転換率（%）",
            #         category_orders={"themes": THEME_ORDER, "尺": BUCKET_ORDER},
            #         color_discrete_sequence=PALETTE,
            #         labels={"themes": "テーマ", "view_eng_rate": "転換率(%)", "尺": "リール尺"},
            #         hover_data={"件数": True},
            #     )
            #     fig_theme_dur.update_traces(textposition="outside")
            #     fig_theme_dur.update_layout(height=440, xaxis_title="", yaxis_title="転換率(%)")
            #     st.plotly_chart(fig_theme_dur, use_container_width=True)
            #     _td = theme_dur[theme_dur["件数"] >= 3]
            #     if not _td.empty:
            #         _best_td = _td.loc[_td["view_eng_rate"].idxmax()]
            #         _worst_td = _td.loc[_td["view_eng_rate"].idxmin()]
            #         st.info(
            #             f"**テーマ × 尺 インサイト** 件数3件以上の組み合わせの中で、"
            #             f"視聴転換率が最も高いのは **{_best_td['themes']} × {_best_td['尺']}**"
            #             f"（{_best_td['view_eng_rate']:.2f}%、{int(_best_td['件数'])}件）、"
            #             f"最も低いのは **{_worst_td['themes']} × {_worst_td['尺']}**"
            #             f"（{_worst_td['view_eng_rate']:.2f}%、{int(_worst_td['件数'])}件）。"
            #             "件数が少ない組み合わせは平均値が不安定なため、参考値としてご覧ください。"
            #         )

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

    _best_wd = w.loc[w["engagement_rate"].idxmax()]
    _worst_wd = w.loc[w["engagement_rate"].idxmin()]
    _best_band = b.loc[b["engagement_rate"].idxmax()]
    _worst_band = b.loc[b["engagement_rate"].idxmin()]
    _pivot_raw = df.pivot_table(index="band", columns="weekday",
                                values="engagement_rate", aggfunc="mean")
    _peak = _pivot_raw.stack().idxmax()
    _peak_er = _pivot_raw.stack().max()
    _peak_band, _peak_wd = _peak
    st.info(
        f"**ベスト投稿タイミング** "
        f"曜日では **{_best_wd['曜日']}**（平均 {_best_wd['engagement_rate']:.2f}%）、"
        f"時間帯では **{_best_band['band']}**（{_best_band['engagement_rate']:.2f}%）が最も高い平均エンゲージメント率を記録。"
        f"組み合わせのピークは **{WD_JP[_peak_wd]} × {_peak_band}**（{_peak_er:.2f}%）です。\n\n"
        f"**避けるべきタイミング** "
        f"**{_worst_wd['曜日']}**（{_worst_wd['engagement_rate']:.2f}%）と"
        f"**{_worst_band['band']}**（{_worst_band['engagement_rate']:.2f}%）は他と比べて平均エンゲージメント率が低く、"
        "投稿スケジュールの見直し余地があります。"
    )

# ===== Tab 4: Content themes =====
with tab4:
    st.subheader("テーマ分布（複数ラベル）")
    st.caption("1件の投稿が複数のテーマに属することがあるため、割合の合計は100%を超えます。")
    mem = expl["theme"].value_counts().reindex(THEME_ORDER).fillna(0).astype(int)
    memdf = pd.DataFrame({"テーマ": mem.index, "投稿数": mem.values,
                          "全投稿に占める割合(%)": (mem.values / len(df) * 100).round(1)})
    er_theme = expl.groupby("theme")["engagement_rate"].mean().reindex(THEME_ORDER).round(2).reset_index()
    # 共通Y軸順序：ER昇順（上が高ER）
    y_order = er_theme.sort_values("engagement_rate")["theme"].tolist()

    memdf["ラベル"] = memdf.apply(
        lambda r: f"{r['全投稿に占める割合(%)']:.1f}%（{r['投稿数']}件）", axis=1)

    colA, colB = st.columns([1.2, 1])
    with colA:
        fig = (px.bar(memdf, x="全投稿に占める割合(%)", y="テーマ", orientation="h",
                      text="ラベル", title="テーマ別投稿割合", color_discrete_sequence=[TED_RED])
               .update_traces(textposition="inside", insidetextanchor="middle")
               .update_layout(showlegend=False, height=360, xaxis_title="割合 (%)",
                               yaxis={"categoryorder": "array", "categoryarray": y_order}))
        st.plotly_chart(fig, use_container_width=True)
    with colB:
        fig = (px.bar(er_theme, x="engagement_rate", y="theme", orientation="h",
                      title="テーマ別平均エンゲージメント率(%)", color_discrete_sequence=["#b77e74"])
               .update_layout(showlegend=False, height=360,
                               yaxis={"categoryorder": "array", "categoryarray": y_order},
                               xaxis_title="エンゲージメント率(%)", yaxis_title=""))
        st.plotly_chart(fig, use_container_width=True)

    _memdf_core = memdf[memdf["テーマ"] != "その他"]
    _best_er_row  = er_theme[er_theme["theme"] != "その他"].loc[er_theme[er_theme["theme"] != "その他"]["engagement_rate"].idxmax()]
    _worst_er_row = er_theme[er_theme["theme"] != "その他"].loc[er_theme[er_theme["theme"] != "その他"]["engagement_rate"].idxmin()]
    _min_post_row = _memdf_core.loc[_memdf_core["投稿数"].idxmin()]
    _ura_pct = memdf[memdf["テーマ"] == "舞台裏・チーム"]["全投稿に占める割合(%)"].values
    _ura_pct_str = f"{_ura_pct[0]:.0f}" if len(_ura_pct) > 0 else "—"
    _kobe_oubo = expl[(expl["account"] == "tedxkobe") & (expl["theme"].isin(["スタッフ・メンバー募集", "チケット・参加申込"]))]
    _kobe_total = expl[expl["account"] == "tedxkobe"]
    _kobe_pct = f"{len(_kobe_oubo) / len(_kobe_total) * 100:.0f}" if len(_kobe_total) > 0 else "—"
    st.info(
        f"**インサイト①「投入少・回報高」の穴 = {_best_er_row['theme']}**　"
        f"平均エンゲージメント率は全テーマ最高（**{_best_er_row['engagement_rate']:.2f}%**）にもかかわらず"
        f"投稿割合は最小（**{_min_post_row['全投稿に占める割合(%)']:.0f}%**）。"
        "回顧・成果型コンテンツは共感を得やすく、増量の余地が最も大きいテーマです。\n\n"
        f"**インサイト②** 舞台裏・チームは投稿割合 **{_ura_pct_str}%** と多いにもかかわらず"
        f"平均エンゲージメント率は最低（**{_worst_er_row['engagement_rate']:.2f}%**）。"
        "主に協賛・餐飲・ブース「紹介型」投稿が大半を占め、受け手との共感が生まれにくい傾向があります。"
    )

    st.subheader("アカウント別 テーマ構成（%）")
    theme_acc = (
        posts_all[posts_all["account"].isin(sel_acc)]
        .explode("themes")
        .groupby(["account", "themes"])
        .size()
        .reset_index(name="件数")
    )
    theme_acc["割合"] = theme_acc.groupby("account")["件数"].transform(lambda x: x / x.sum() * 100).round(1)
    theme_order_map = {t: i for i, t in enumerate(THEME_ORDER)}
    theme_acc["theme_order"] = theme_acc["themes"].map(theme_order_map)
    theme_acc = theme_acc.sort_values("theme_order")
    THEME_PALETTE = {
        "スタッフ・メンバー募集": "#772315",
        "チケット・参加申込":   "#e05c3a",
        "スピーカー紹介":     "#b77e74",
        "理念・メッセージ":    "#ecbca4",
        "舞台裏・チーム":     "#c22d0e",
        "イベント回顧":      "#492822",
        "その他":          "#dac1bd",
    }
    fig_theme = px.bar(
        theme_acc, x="割合", y="account", color="themes", orientation="h",
        text="割合",
        title="アカウント別 コンテンツテーマ構成比（%）",
        color_discrete_map=THEME_PALETTE,
        category_orders={"themes": THEME_ORDER},
    )
    fig_theme.update_traces(texttemplate="%{text:.0f}%", textposition="inside", insidetextanchor="middle")
    fig_theme.update_layout(
        barmode="stack", height=380, showlegend=True,
        xaxis_title="割合 (%)", yaxis_title="",
        legend_title="テーマ",
        xaxis=dict(range=[0, 100]),
    )
    st.plotly_chart(fig_theme, use_container_width=True)

    _utokyo_ura = theme_acc[
        (theme_acc["account"] == "tedxutokyo") & (theme_acc["themes"] == "舞台裏・チーム")
    ]["割合"]
    _utokyo_pct = f"{_utokyo_ura.values[0]:.0f}" if len(_utokyo_ura) > 0 else "—"
    st.info(
        "**インサイト③ アカウントごとの戦略差**　"
        f"awaji／kyoto は理念・メッセージ重視、kobe はスタッフ募集・チケット系に偏重（**{_kobe_pct}%**）、"
        "keiou はスピーカー予告を軸にしており、上のグラフで各アカウントの構成比を確認できます。\n\n"
        f"**インサイト④** tedxutokyo の平均エンゲージメント率が全体最低な理由：コンテンツの **{_utokyo_pct}%** が舞台裏・チーム"
        "（贊助／餐飲／攤位系列）に偏っており、このカテゴリは平均エンゲージメント率が最も低いため、全体平均を押し下げています。"
    )

    st.divider()
    st.subheader("テーマ別 キーワード分析とトップ投稿")
    pick = st.selectbox("テーマを選択", THEME_ORDER, index=0)
    sub = df[df["themes"].apply(lambda L: pick in L)]
    st.caption(f"「{pick}」{len(sub):,} 件　｜　平均エンゲージメント率 "
               f"{sub['engagement_rate'].mean():.2f}%　｜　平均いいね数 {sub['likes'].mean():.0f}")

    _kw_ver_key = f"kw_ver_{pick}"
    _kw_sel_key = f"kw_selected_{pick}"
    if _kw_ver_key not in st.session_state:
        st.session_state[_kw_ver_key] = 0
    if _kw_sel_key not in st.session_state:
        st.session_state[_kw_sel_key] = None
    _kw_ver = st.session_state[_kw_ver_key]

    kw = extract_keywords(sub["caption"]).most_common(30)
    k1, k2 = st.columns(2)
    kw_words = [w for w, _ in kw]

    if kw:
        kdf = pd.DataFrame(kw, columns=["キーワード", "件数"])
        fig = px.treemap(kdf, path=["キーワード"], values="件数",
                         title=f"「{pick}」キーワードクラウド（出現頻度）— タイルをクリックで投稿を表示",
                         color="件数", color_continuous_scale="Reds")
        fig.update_layout(height=400, margin=dict(t=40, l=0, r=0, b=0))
        ev1 = k1.plotly_chart(fig, use_container_width=True,
                               on_select="rerun", key=f"kw_freq_{pick}_{_kw_ver}")

        er_rows = []
        for word, _ in kw:
            mask = sub["caption"].str.contains(re.escape(word), case=False, na=False)
            er = sub.loc[mask, "engagement_rate"].mean()
            er_rows.append({"キーワード": word, "平均ER(%)": round(er, 2)})
        kw_er_df = pd.DataFrame(er_rows)
        fig2 = px.treemap(kw_er_df, path=["キーワード"], values="平均ER(%)",
                          title=f"「{pick}」キーワード別 平均エンゲージメント率(%) — タイルをクリックで投稿を表示",
                          color="平均ER(%)", color_continuous_scale="Reds",
                          hover_data={"平均ER(%)": ":.2f"})
        fig2.update_layout(height=400, margin=dict(t=40, l=0, r=0, b=0))
        ev2 = k2.plotly_chart(fig2, use_container_width=True,
                               on_select="rerun", key=f"kw_er_{pick}_{_kw_ver}")

        clicked_label = None
        for ev in (ev1, ev2):
            pts = (ev or {}).get("selection", {}).get("points", [])
            if pts:
                label = pts[0].get("label") or pts[0].get("id", "")
                if label in kw_words:
                    clicked_label = label
                    break

        if clicked_label:
            if st.session_state[_kw_sel_key] == clicked_label:
                # 同じタイルを再クリック → 選択解除してチャートをリセット
                st.session_state[_kw_sel_key] = None
                st.session_state[_kw_ver_key] += 1
                st.rerun()
            else:
                st.session_state[_kw_sel_key] = clicked_label
    else:
        k1.info("キーワードが十分にありません。")

    selected_kw = st.session_state.get(_kw_sel_key)

    if selected_kw:
        st.markdown(f"**「{selected_kw}」を含む投稿（平均エンゲージメント率降順 / {sub[sub['caption'].str.contains(re.escape(selected_kw), case=False, na=False)].shape[0]} 件）**")
        mask = sub["caption"].str.contains(re.escape(selected_kw), case=False, na=False)
        kw_posts = sub[mask].sort_values("engagement_rate", ascending=False).copy()
        kw_posts["日付"] = kw_posts["dt"].dt.strftime("%Y-%m-%d")
        kw_posts["抜粋"] = kw_posts["caption"].str.replace("\n", " ", regex=False).str.slice(0, 90)
        st.dataframe(
            kw_posts[["account", "日付", "type_jp", "likes", "comments",
                       "engagement_rate", "抜粋", "url"]].rename(
                columns={"account": "アカウント", "type_jp": "タイプ", "likes": "いいね",
                         "comments": "コメント", "engagement_rate": "エンゲージメント率(%)", "url": "リンク"}),
            use_container_width=True, hide_index=True,
            column_config={"リンク": st.column_config.LinkColumn("リンク")})
    else:
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
