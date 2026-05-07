# UI 重构计划

> 状态: 待执行
> 前置条件: P0-1（确认工作区干净）、P0-2（新建分支）
> 目标: 将 1268 行 `ui/app.py` 拆分为模块化结构，消除 StreamlitDuplicateElementId 风险

---

## 目标结构

```
ui/
  app.py                    # 入口 + 轻量路由（~50行）
  state.py                  # init_session_state() + 所有 key 常量
  constants.py              # 页面列表、模板字典、版本号
  styles.py                 # st.set_page_config + 自定义 CSS
  __init__.py
  components/
    __init__.py
    stats_cards.py          # 首页 4 列 metric 统计卡片
    search_result_table.py  # 检索结果 st.dataframe 渲染
    pending_papers_table.py # 全文获取待下载列表
    page_message.py         # show_page_message() 跨页面消息
    keyword_templates.py    # 药物化学关键词模板 expander
  services/
    __init__.py
    cache.py                # @st.cache_resource / @st.cache_data 函数
    search_service.py       # _execute_search 核心逻辑（不写 session_state）
    fulltext_service.py     # resolve / download / batch_download 调用封装
    library_service.py      # 文献库搜索逻辑
  pages/
    __init__.py
    home.py                 # 首页 — 系统概览
    paper_search.py         # 文献检索（关键词 + 期刊监控）
    library.py              # 我的文献库
    fulltext.py             # 全文获取 / PDF 下载
    pdf_convert.py          # PDF 转换
    rag.py                  # RAG 智能问答
    group_profile.py        # 课题组画像
    writing.py              # 写作辅助
    settings.py             # 系统设置
```

---

## Step 1: 给所有 Streamlit 控件补唯一 key

### 修改范围

- 只修改 `ui/app.py`

### 具体操作

- [ ] 搜索所有 `st.button(` 调用，确认每个有 `key=`
- [ ] 搜索所有 `st.text_input(` / `st.text_area(` / `st.selectbox(` / `st.radio(` 调用，确认每个有 `key=`
- [ ] 搜索所有 `st.checkbox(` / `st.multiselect(` / `st.number_input(` 调用，确认每个有 `key=`
- [ ] 特别关注全文获取页面的按钮（单篇操作区 `resolve_btn` / `download_btn` / `mark_review_btn`）
- [ ] 特别关注文献库页面的 `st.selectbox`（`library_source`）— 已有 key，确认无冲突
- [ ] 将 4 个未在 `init_session_state()` 中声明的 key 加入：`search_mode`、`rag_question`、`writing_type`、`writing_input`

### 不允许改什么

- 不改任何业务逻辑
- 不改任何 session_state 键名
- 不改页面布局
- 不改 `src/` 下的任何文件
- 不改 `api/` 下的任何文件

### 验收标准

- [ ] `streamlit run ui/app.py` 启动无 `StreamlitDuplicateElementId` 异常
- [ ] 遍历 9 个页面，每个页面的每个按钮点击一次，无报错
- [ ] `python run.py test` 110 passed

### 测试命令

```bash
python run.py test
```

### commit message

```
fix(ui): add explicit keys to all Streamlit widgets to prevent DuplicateElementId
```

---

## Step 2: 抽出 state.py / constants.py / styles.py

### 修改范围

- 新建: `ui/state.py`、`ui/constants.py`、`ui/styles.py`、`ui/__init__.py`
- 修改: `ui/app.py`

### 具体操作

**`ui/state.py`**:
- [ ] 搬入 `init_session_state()` 函数
- [ ] 将所有 session_state key 定义为模块级字符串常量（便于跨文件引用）:
  ```python
  KEY_CURRENT_PAGE = "current_page"
  KEY_SEARCH_KEYWORD = "search_keyword"
  KEY_SEARCH_RESULTS = "search_results"
  # ... 全部 34 个 key
  ```
- [ ] `init_session_state()` 内部使用这些常量（而非字符串字面量）

**`ui/constants.py`**:
- [ ] 搬入 `page_options` 列表（9 个页面名）
- [ ] 搬入药物化学关键词模板字典 `KEYWORD_TEMPLATES`
- [ ] 搬入版本号 `VERSION = "0.2.0"`
- [ ] 搬入 API 数据源选项列表 `SEARCH_SOURCES`
- [ ] 搬入排序方式选项 `SORT_OPTIONS`

**`ui/styles.py`**:
- [ ] 搬入 `st.set_page_config()` 调用
- [ ] 如有自定义 CSS 在此定义

**`ui/app.py` 修改**:
- [ ] `from ui.state import init_session_state, KEY_*`
- [ ] `from ui.constants import PAGE_OPTIONS, KEYWORD_TEMPLATES, VERSION, ...`
- [ ] `from ui.styles import set_page_config` (或直接在 app.py 开头调用)
- [ ] 移除被搬走的代码块

### 不允许改什么

- 不改任何 session_state 键的语义和顺序
- 不改页面功能

### 验收标准

- [ ] `streamlit run ui/app.py` 启动无 import 错误
- [ ] 所有页面功能与拆分前一致
- [ ] `python run.py test` 110 passed

### 测试命令

```bash
python -c "from ui.state import init_session_state; print('state OK')"
python -c "from ui.constants import PAGE_OPTIONS; print('constants OK')"
python -c "from ui.styles import *; print('styles OK')"
python run.py test
```

### commit message

```
refactor(ui): extract state, constants, and styles into separate modules
```

---

## Step 3: 抽出 components

### 修改范围

- 新建: `ui/components/` 目录及文件
- 修改: `ui/app.py`（替换内联代码为 import 调用）

### 具体操作

- [ ] `ui/components/page_message.py`: 搬入 `show_page_message()`
- [ ] `ui/components/stats_cards.py`: 搬入首页统计卡片渲染代码
  ```python
  def render_stats_cards(db_stats: dict, ft_stats: dict) -> None:
      """渲染首页 4 列统计卡片"""
  ```
- [ ] `ui/components/search_result_table.py`: 搬入 `_display_search_results()` 中的表格渲染
  ```python
  def render_search_result_table(results: list, total_count: int, errors: list) -> None:
      """渲染检索结果表格和统计信息"""
  ```
- [ ] `ui/components/pending_papers_table.py`: 搬入全文获取页面的待下载列表渲染
- [ ] `ui/components/keyword_templates.py`: 搬入药物化学关键词模板 expander

### 原则

- 每个组件函数接收参数，不直接读 `st.session_state`
- 组件可以调用 `st.*` 渲染 widget，但不写业务逻辑
- 组件的 key 由调用方传入或在组件内基于传入参数生成

### 不允许改什么

- 不改 session_state 读写逻辑（留在页面文件中）
- 不改后端调用

### 验收标准

- [ ] 所有页面渲染结果与拆分前完全一致（手动对比截图或逐页对比）
- [ ] `python run.py test` 110 passed

### 测试命令

```bash
python -c "from ui.components.page_message import show_page_message; print('components OK')"
python run.py test
```

### commit message

```
refactor(ui): extract reusable components into ui/components/
```

---

## Step 4: 抽出 services

### 修改范围

- 新建: `ui/services/` 目录及文件
- 修改: `ui/app.py`（替换内联调用为 service 调用）

### 具体操作

- [ ] `ui/services/cache.py`: 搬入 `get_cached_repository()`、`get_cached_download_stats()`、`get_cached_db_stats()`、`clear_stats_cache()`
- [ ] `ui/services/search_service.py`: 搬入 `_execute_search()` 和 `_restore_last_search()` 核心逻辑
  ```python
  def execute_search(keywords, sources, year_from, year_to, max_results, sort_by, oa_only, nsc_boost, search_mode) -> dict:
      """执行检索，返回 {results, total_count, errors, last_query}，不写 session_state"""
  ```
- [ ] `ui/services/fulltext_service.py`: 搬入全文获取操作封装
- [ ] `ui/services/library_service.py`: 搬入文献库搜索逻辑

### 原则

- service 函数**不直接操作 `st.session_state`**
- service 函数返回结果字典/对象
- 页面回调中调用 service，然后将返回结果写入 session_state

### 不允许改什么

- 不改 session_state 键名
- 不改业务逻辑语义

### 验收标准

- [ ] 所有页面功能与拆分前一致
- [ ] 检索→结果展示→页面切换→结果保留→清空结果 完整流程正常
- [ ] `python run.py test` 110 passed

### 测试命令

```bash
python -c "from ui.services.cache import get_cached_repository; print('services OK')"
python run.py test
```

### commit message

```
refactor(ui): extract backend service calls into ui/services/
```

---

## Step 5: 拆 pages

### 修改范围

- 新建: `ui/pages/` 目录及 9 个页面文件
- 修改: `ui/app.py`（替换 if/elif 链为路由表）

### 具体操作

- [ ] 每个页面文件导出一个 `render()` 函数
- [ ] `ui/app.py` 变为:
  ```python
  from ui.pages import home, paper_search, library, fulltext, pdf_convert, rag, group_profile, writing, settings

  PAGE_MAP = {
      "首页 — 系统概览": home.render,
      "文献检索": paper_search.render,
      "我的文献库": library.render,
      "全文获取 / PDF 下载": fulltext.render,
      "PDF 转换": pdf_convert.render,
      "RAG 智能问答": rag.render,
      "课题组画像": group_profile.render,
      "写作辅助": writing.render,
      "系统设置": settings.render,
  }

  # 路由
  page_key = st.session_state.get("current_page", "首页 — 系统概览")
  render_func = PAGE_MAP.get(page_key)
  if render_func:
      render_func()
  ```

### 不允许改什么

- 不改任何 session_state 键名
- 不改任何组件的外观和行为
- 不改 import 路径（页面 import 的 `src/` 模块保持不变）

### 验收标准

- [ ] 所有 9 个页面切换正常
- [ ] 页面切换后状态不丢失（检索结果、筛选条件等保留）
- [ ] "恢复最近检索结果"按钮正常
- [ ] "清空"按钮正常
- [ ] `python run.py test` 110 passed

### 测试命令

```bash
python -c "from ui.pages import home, paper_search; print('pages OK')"
python run.py test
```

### commit message

```
refactor(ui): split monolithic app.py into per-page modules under ui/pages/
```

---

## Step 6: 优化文献检索页（P1 阶段，可后续进行）

（在 Step 5 完成后，修改 `ui/pages/paper_search.py` 即可，不影响其他页面）

### commit message

```
feat(ui): add pagination and search history to search page
```

---

## Step 7: 优化全文下载页（P1 阶段，可后续进行）

### commit message

```
feat(ui): add progress bar and tabs to fulltext page
```

---

## Step 8: 验收和提交

- [ ] `python run.py test` 110 passed
- [ ] `streamlit run ui/app.py` 遍历 9 页无异常
- [ ] `git log --oneline` 确认每个 step 有独立 commit
- [ ] 合并回 master: `git checkout master && git merge feature/ui-refactor`

---

## 总体原则

1. **每步独立 commit** — 不把多个 step 合并成一个 commit
2. **每步后跑测试** — `python run.py test` 确认 110 passed
3. **不破坏功能** — 任何时候 `streamlit run ui/app.py` 应该可用
4. **不提前优化** — 先拆结构，再优化功能（Step 6/7 在 Step 5 之后再做）
5. **不碰后端** — `src/` 和 `api/` 下的文件不修改
