import streamlit as st
import pandas as pd
import re
import sqlite3
import io
import os

# === 数据库处理类 ===
class RuleDatabase:
    def __init__(self):
        self.db_path = "rules_database.db"
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger TEXT NOT NULL,
                map_word TEXT NOT NULL,
                col TEXT NOT NULL
            )
        ''')
        self.conn.commit()

    def add_rule(self, trigger, map_word, col):
        self.cursor.execute('INSERT INTO rules (trigger, map_word, col) VALUES (?,?,?)', (trigger, map_word, col))
        self.conn.commit()

    def batch_import_rules(self, rule_list):
        count_ok = 0
        for trig, mapw, col in rule_list:
            if trig and mapw:
                self.add_rule(trig, mapw, col)
                count_ok += 1
        return count_ok

    def delete_rule(self, rule_id):
        self.cursor.execute('DELETE FROM rules WHERE id=?', (rule_id,))
        self.conn.commit()

    def delete_all_rules(self):
        self.cursor.execute('DELETE FROM rules')
        self.conn.commit()

    def get_all_rules(self):
        self.cursor.execute('SELECT id, trigger, map_word, col FROM rules')
        return self.cursor.fetchall()

    def get_rule_count(self):
        self.cursor.execute('SELECT COUNT(*) FROM rules')
        return self.cursor.fetchone()[0]

# === 初始化 ===
if 'db' not in st.session_state:
    st.session_state.db = RuleDatabase()
if 'df' not in st.session_state:
    st.session_state.df = None
if 'custom_columns' not in st.session_state:
    if os.path.exists("columns.config"):
        with open("columns.config", "r", encoding="utf-8") as f:
            st.session_state.custom_columns = [i.strip() for i in f.readlines() if i.strip()]
    else:
        st.session_state.custom_columns = []

st.set_page_config(page_title="超强模糊匹配", layout="wide")
st.title("🚀 超强模糊匹配提取工具 (网页版)")

# === 侧边栏 ===
with st.sidebar:
    st.header("📁 数据管理")
    uploaded_file = st.file_uploader("导入业务表格", type=["xlsx", "csv"])
    if uploaded_file:
        if st.button("确认读取并初始化预览"):
            df = pd.read_csv(uploaded_file, usecols=[0], dtype=str, keep_default_na=False) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file, usecols=[0], dtype=str, keep_default_na=False)
            df.columns = ["原始内容"]
            for col in st.session_state.custom_columns: df[col] = ""
            st.session_state.df = df
            st.success("读取成功！")

    st.divider()
    st.header("🛠️ 列管理")
    new_col = st.text_input("新增列名")
    if st.button("➕ 添加新列"):
        if new_col and new_col not in st.session_state.custom_columns:
            st.session_state.custom_columns.append(new_col)
            with open("columns.config", "w", encoding="utf-8") as f: f.write("\n".join(st.session_state.custom_columns))
            if st.session_state.df is not None: st.session_state.df[new_col] = ""
            st.rerun()

# === 主界面 ===
if st.session_state.df is not None:
    tab1, tab2, tab3 = st.tabs(["🔍 符号提取", "⚙️ 规则匹配中心", "📊 数据下载"])

    with tab1:
        st.subheader("提取符号内容")
        c1, c2, c3, c4 = st.columns(4)
        with c1: l_sym = st.text_input("左符号")
        with c2: r_sym = st.text_input("右符号")
        with c3: target_col = st.selectbox("目标列", st.session_state.df.columns)
        if st.button("执行提取"):
            pat = re.compile(re.escape(l_sym) + r"(.*?)" + re.escape(r_sym))
            st.session_state.df[target_col] = st.session_state.df["原始内容"].apply(lambda x: (pat.search(str(x)).group(1).strip() if pat.search(str(x)) else ""))
            st.success("提取完成")

    with tab2:
        # --- 批量导入规则区域 ---
        st.subheader("📥 批量导入规则表")
        rule_file = st.file_uploader("上传包含规则的表格 (Excel/CSV)", type=["xlsx", "csv"], key="rule_upload")
        if rule_file:
            df_rule_raw = pd.read_excel(rule_file, header=None) if rule_file.name.endswith(".xlsx") else pd.read_csv(rule_file, header=None)
            col_options = [f"第{i+1}列" for i in range(df_rule_raw.shape[1])]
            
            b1, b2, b3, b4 = st.columns(4)
            with b1: trig_idx = st.selectbox("触发词所在列", range(len(col_options)), format_func=lambda x: col_options[x])
            with b2: map_idx = st.selectbox("对应值所在列", range(len(col_options)), format_func=lambda x: col_options[x], index=min(1, len(col_options)-1))
            with b3: target_rule_col = st.selectbox("归类到哪个目标列", st.session_state.custom_columns)
            with b4:
                st.write("确认导入")
                if st.button("开始批量导入"):
                    rules_to_add = []
                    for _, row in df_rule_raw.iterrows():
                        t, m = str(row[trig_idx]), str(row[map_idx])
                        if t and m: rules_to_add.append((t, m, target_rule_col))
                    count = st.session_state.db.batch_import_rules(rules_to_add)
                    st.success(f"成功导入 {count} 条新规则！")
                    st.rerun()

        st.divider()
        st.subheader("📝 单条规则管理")
        rc1, rc2, rc3, rc4 = st.columns(4)
        with rc1: t_trig = st.text_input("触发词")
        with rc2: t_map = st.text_input("对应值")
        with rc3: t_col = st.selectbox("目标列", st.session_state.custom_columns, key="single_rule_col")
        if st.button("添加单条"):
            if t_trig and t_map:
                st.session_state.db.add_rule(t_trig, t_map, t_col)
                st.rerun()

        st.divider()
        all_rules = st.session_state.db.get_all_rules()
        if all_rules:
            with st.expander(f"查看/删除规则 (共{len(all_rules)}条)"):
                rule_df = pd.DataFrame(all_rules, columns=["ID", "触发词", "对应值", "目标列"])
                st.dataframe(rule_df, use_container_width=True)
                del_id = st.number_input("删除 ID", step=1, value=0)
                if st.button("确认删除"):
                    st.session_state.db.delete_rule(del_id)
                    st.rerun()
                if st.button("🔥 清空全部"):
                    st.session_state.db.delete_all_rules(); st.rerun()

        st.divider()
        if st.button("✅ 执行全量模糊匹配", type="primary"):
            rules = st.session_state.db.get_all_rules()
            def apply_fuzzy(row):
                text_clean = re.sub(r"\s+", "", str(row["原始内容"]))
                for r in rules:
                    _, r_trig, r_map, r_col = r
                    if re.sub(r"\s+", "", str(r_trig)) in text_clean: row[r_col] = r_map
                return row
            st.session_state.df = st.session_state.df.apply(apply_fuzzy, axis=1)
            st.success("匹配完成！")

    with tab3:
        st.subheader("预览与导出")
        st.dataframe(st.session_state.df, use_container_width=True)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer: st.session_state.df.to_excel(writer, index=False)
        st.download_button("📥 下载 Excel", output.getvalue(), "processed.xlsx")
else:
    st.info("💡 请先在左侧上传表格并点击确认读取。")
