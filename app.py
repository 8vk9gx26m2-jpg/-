import streamlit as st
import pandas as pd
import re
import sqlite3
import io
import os


# === 1. 数据库处理类 (保持文件名一致，确保数据不丢失) ===
class RuleDatabase:
    def __init__(self):
        # 使用你原来的数据库文件名
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


# === 2. 初始化环境与状态 ===
if 'db' not in st.session_state:
    st.session_state.db = RuleDatabase()
if 'df' not in st.session_state:
    st.session_state.df = None
if 'custom_columns' not in st.session_state:
    # 尝试加载之前的列配置
    if os.path.exists("columns.config"):
        with open("columns.config", "r", encoding="utf-8") as f:
            st.session_state.custom_columns = [i.strip() for i in f.readlines() if i.strip()]
    else:
        st.session_state.custom_columns = []

# === 3. 网页布局配置 ===
st.set_page_config(page_title="超强模糊匹配工具", layout="wide")
st.title("🚀 超强模糊匹配提取工具 (网页版)")

# === 4. 侧边栏：文件导入与列管理 ===
with st.sidebar:
    st.header("📁 数据管理")
    uploaded_file = st.file_uploader("导入业务表格", type=["xlsx", "csv"])

    if uploaded_file:
        if st.button("确认读取并初始化预览"):
            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file, usecols=[0], dtype=str, keep_default_na=False)
            else:
                df = pd.read_excel(uploaded_file, usecols=[0], dtype=str, keep_default_na=False)
            df.columns = ["原始内容"]
            # 自动补全自定义列
            for col in st.session_state.custom_columns:
                if col not in df.columns:
                    df[col] = ""
            st.session_state.df = df
            st.success("读取成功！")

    st.divider()
    st.header("🛠️ 列管理")
    new_col = st.text_input("新增列名")
    if st.button("➕ 添加新列"):
        if new_col and new_col not in st.session_state.custom_columns:
            st.session_state.custom_columns.append(new_col)
            # 同步更新本地配置
            with open("columns.config", "w", encoding="utf-8") as f:
                f.write("\n".join(st.session_state.custom_columns))
            if st.session_state.df is not None:
                st.session_state.df[new_col] = ""
            st.rerun()

    if st.session_state.custom_columns:
        col_to_del = st.selectbox("要删除的列", st.session_state.custom_columns)
        if st.button("🗑️ 删除该列"):
            st.session_state.custom_columns.remove(col_to_del)
            with open("columns.config", "w", encoding="utf-8") as f:
                f.write("\n".join(st.session_state.custom_columns))
            if st.session_state.df is not None:
                st.session_state.df.drop(columns=[col_to_del], inplace=True)
            st.rerun()

# === 5. 主界面逻辑 ===
if st.session_state.df is not None:
    tab1, tab2, tab3 = st.tabs(["🔍 符号中间提取", "⚙️ 规则匹配中心", "📊 数据下载"])

    # --- TAB 1: 符号提取 ---
    with tab1:
        st.subheader("提取两符号中间内容")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            l_sym = st.text_input("左符号", placeholder="如 [")
        with c2:
            r_sym = st.text_input("右符号", placeholder="如 ]")
        with c3:
            target_col = st.selectbox("存入哪一列", st.session_state.df.columns)
        with c4:
            st.write("操作")
            if st.button("开始提取内容"):
                if l_sym and r_sym:
                    pat = re.compile(re.escape(l_sym) + r"(.*?)" + re.escape(r_sym))


                    def do_extract(text):
                        res = pat.search(str(text))
                        return res.group(1).strip() if res else ""


                    st.session_state.df[target_col] = st.session_state.df["原始内容"].apply(do_extract)
                    st.success("提取操作已应用！")

    # --- TAB 2: 规则匹配管理 ---
    with tab2:
        st.subheader("匹配规则设置")
        rc1, rc2, rc3, rc4 = st.columns(4)
        with rc1:
            trig = st.text_input("触发关键词")
        with rc2:
            mapw = st.text_input("对应的结果值")
        with rc3:
            r_col = st.selectbox("匹配成功存入", st.session_state.custom_columns, key="rule_sel")
        with rc4:
            st.write("操作")
            if st.button("添加单条规则"):
                if trig and mapw:
                    st.session_state.db.add_rule(trig, mapw, r_col)
                    st.rerun()

        st.divider()
        st.write(f"当前库中共有 **{st.session_state.db.get_rule_count()}** 条规则")

        # 显示规则列表
        all_rules = st.session_state.db.get_all_rules()
        if all_rules:
            with st.expander("查看/删除当前所有规则"):
                rule_df = pd.DataFrame(all_rules, columns=["ID", "触发词", "对应值", "目标列"])
                st.dataframe(rule_df, use_container_width=True)
                del_id = st.number_input("输入规则 ID 并点击删除", step=1, value=0)
                if st.button("❌ 确认删除 ID 规则"):
                    st.session_state.db.delete_rule(del_id)
                    st.rerun()
                if st.button("🔥 清空整个规则库"):
                    st.session_state.db.delete_all_rules()
                    st.rerun()

        st.divider()
        if st.button("✅ 立即执行全量模糊匹配", type="primary"):
            rules = st.session_state.db.get_all_rules()


            def apply_fuzzy(row):
                text_clean = re.sub(r"\s+", "", str(row["原始内容"]))
                for r in rules:
                    _, r_trig, r_map, r_col = r
                    trig_clean = re.sub(r"\s+", "", str(r_trig))
                    if trig_clean in text_clean:
                        row[r_col] = r_map
                return row


            with st.spinner("正在进行深度匹配..."):
                st.session_state.df = st.session_state.df.apply(apply_fuzzy, axis=1)
            st.success("模糊匹配完成！")

    # --- TAB 3: 数据下载 ---
    with tab3:
        st.subheader("最终结果预览")
        st.dataframe(st.session_state.df, use_container_width=True)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            st.session_state.df.to_excel(writer, index=False)

        st.download_button(
            label="📥 下载处理后的 Excel 表格",
            data=output.getvalue(),
            file_name="processed_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("💡 操作指南：请先在左侧侧边栏上传你需要处理的 Excel 或 CSV 表格。")