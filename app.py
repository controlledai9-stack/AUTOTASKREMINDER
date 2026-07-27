"""AI Daily Progress Tracker - Streamlit UI.

Run with:  streamlit run app.py

This file is intentionally UI-only: all business logic (CRUD, progress
math, streaks, email sending) lives in the ``src/`` package. The app
renders a dashboard, a task manager, an analytics view, and a settings
panel across four tabs.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import export_service, git_sync, progress_calculator, streak_tracker, task_manager
from src.config import (
    DEFAULT_CATEGORIES,
    PRIORITY_LEVELS,
    SCHEDULED_SEND_TIMES,
    validate_email_config,
)
from src.database import initialize_database
from src.email_service import get_recent_email_log, motivational_message
from src.utils import format_timestamp_for_display, today_iso

# ---------------------------------------------------------------------------
# Page configuration & one-time setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Daily Progress Tracker",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_database()

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "editing_task_id" not in st.session_state:
    st.session_state.editing_task_id = None


# ---------------------------------------------------------------------------
# Theming - inject CSS based on the dark_mode toggle
# ---------------------------------------------------------------------------
def inject_theme_css(dark: bool) -> None:
    """Inject custom CSS for the selected theme and shared component styling."""
    if dark:
        bg, card_bg, text, subtext, border = "#0F1117", "#1A1D29", "#F3F4F6", "#9CA3AF", "#2D3040"
    else:
        bg, card_bg, text, subtext, border = "#F5F6FA", "#FFFFFF", "#111827", "#6B7280", "#E5E7EB"

    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {bg}; color: {text}; }}
        div[data-testid="stMetric"] {{
            background-color: {card_bg};
            border: 1px solid {border};
            border-radius: 12px;
            padding: 14px 16px;
        }}
        div[data-testid="stMetricLabel"] {{ color: {subtext} !important; }}
        .task-card {{
            background-color: {card_bg};
            border: 1px solid {border};
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 8px;
        }}
        .priority-High {{ border-left: 4px solid #EF4444; }}
        .priority-Medium {{ border-left: 4px solid #F59E0B; }}
        .priority-Low {{ border-left: 4px solid #10B981; }}
        .subtle {{ color: {subtext}; font-size: 12px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_theme_css(st.session_state.dark_mode)

# ---------------------------------------------------------------------------
# Sidebar - filters, search, quick add, theme toggle
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ✅ Progress Tracker")
    st.toggle("🌙 Dark mode", key="dark_mode")

    st.markdown("---")
    st.markdown("### ➕ Quick Add Task")
    with st.form("quick_add_form", clear_on_submit=True):
        new_title = st.text_input("Title", placeholder="e.g. Finish project proposal")
        new_description = st.text_area("Description (optional)", height=68)
        col_a, col_b = st.columns(2)
        with col_a:
            new_category = st.selectbox("Category", DEFAULT_CATEGORIES)
        with col_b:
            new_priority = st.selectbox("Priority", PRIORITY_LEVELS, index=1)
        new_due_date = st.date_input("Due date (optional)", value=None)
        submitted = st.form_submit_button("Add Task", use_container_width=True)

        if submitted:
            if not new_title.strip():
                st.error("Please enter a task title.")
            else:
                task_manager.create_task(
                    title=new_title,
                    description=new_description,
                    category=new_category,
                    priority=new_priority,
                    due_date=new_due_date.isoformat() if new_due_date else None,
                )
                st.success(f"Added: {new_title}")
                st.rerun()

    st.markdown("---")
    st.markdown("### 🔍 Filter & Search")
    search_query = st.text_input("Search tasks", placeholder="Search by title or notes...")
    existing_categories = ["All"] + sorted(
        set(DEFAULT_CATEGORIES) | set(task_manager.get_distinct_categories())
    )
    filter_category = st.selectbox("Category", existing_categories)
    filter_priority = st.selectbox("Priority", ["All"] + PRIORITY_LEVELS)
    filter_status = st.selectbox("Status", ["All", "pending", "completed"])

# ---------------------------------------------------------------------------
# Shared data fetch (used by multiple tabs)
# ---------------------------------------------------------------------------
all_tasks = task_manager.get_all_tasks()
filtered_tasks = task_manager.get_all_tasks(
    category=filter_category,
    priority=filter_priority,
    status=filter_status,
    search_query=search_query,
)
progress = progress_calculator.compute_progress(all_tasks)
streak_tracker.record_snapshot(progress)
current_streak = streak_tracker.compute_current_streak()
longest_streak = streak_tracker.compute_longest_streak()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_dashboard, tab_tasks, tab_analytics, tab_settings = st.tabs(
    ["📊 Dashboard", "📝 Tasks", "📈 Analytics", "⚙️ Settings"]
)

# ===================== DASHBOARD TAB =====================
with tab_dashboard:
    st.markdown(f"#### {motivational_message(progress.completed_pct)}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Completed", f"{progress.completed_tasks}", f"{progress.completed_pct:.1f}%")
    m2.metric("Pending", f"{progress.pending_tasks}", f"-{progress.remaining_pct:.1f}% remaining")
    m3.metric("Current Streak", f"🔥 {current_streak} days")
    m4.metric("Longest Streak", f"🏆 {longest_streak} days")

    st.markdown("##### Overall Completion")
    st.progress(progress.completed_pct / 100 if progress.total_tasks else 0.0)

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("##### By Category")
        if progress.by_category:
            cat_df = pd.DataFrame(
                [{"Category": k, "Completed": v["completed"], "Pending": v["pending"]} for k, v in progress.by_category.items()]
            )
            fig = go.Figure()
            fig.add_bar(name="Completed", x=cat_df["Category"], y=cat_df["Completed"], marker_color="#10B981")
            fig.add_bar(name="Pending", x=cat_df["Category"], y=cat_df["Pending"], marker_color="#F59E0B")
            fig.update_layout(
                barmode="stack",
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color=("#F3F4F6" if st.session_state.dark_mode else "#111827"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Add some tasks to see category breakdown.")

    with col_right:
        st.markdown("##### Completion Split")
        if progress.total_tasks:
            fig = go.Figure(
                data=[
                    go.Pie(
                        labels=["Completed", "Pending"],
                        values=[progress.completed_tasks, progress.pending_tasks],
                        hole=0.6,
                        marker_colors=["#10B981", "#F59E0B"],
                    )
                ]
            )
            fig.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font_color=("#F3F4F6" if st.session_state.dark_mode else "#111827"),
                showlegend=True,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No tasks yet - add your first one from the sidebar!")

# ===================== TASKS TAB =====================
with tab_tasks:
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.markdown(f"#### {len(filtered_tasks)} task(s) shown")
    with top_col2:
        if st.button("🗑️ Clear all completed", use_container_width=True):
            removed = task_manager.delete_all_completed()
            st.success(f"Removed {removed} completed task(s).")
            st.rerun()

    if not filtered_tasks:
        st.info("No tasks match your current filters. Try adjusting them, or add a new task from the sidebar.")

    for task in filtered_tasks:
        with st.container():
            st.markdown(f'<div class="task-card priority-{task.priority}">', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([0.5, 5, 1.5, 1.5])

            with c1:
                is_done = st.checkbox(
                    "", value=task.is_completed, key=f"chk_{task.id}", label_visibility="collapsed"
                )
                if is_done != task.is_completed:
                    task_manager.set_task_status(task.id, is_done)
                    st.rerun()

            with c2:
                strike = "text-decoration: line-through; opacity: 0.55;" if task.is_completed else ""
                st.markdown(f"**<span style='{strike}'>{task.title}</span>**", unsafe_allow_html=True)
                if task.description:
                    st.markdown(f"<span class='subtle'>{task.description}</span>", unsafe_allow_html=True)
                due_text = f" · Due {task.due_date}" if task.due_date else ""
                st.markdown(
                    f"<span class='subtle'>{task.category} · {task.priority} priority{due_text}</span>",
                    unsafe_allow_html=True,
                )

            with c3:
                if st.button("✏️ Edit", key=f"edit_{task.id}", use_container_width=True):
                    st.session_state.editing_task_id = task.id
                    st.rerun()

            with c4:
                if st.button("🗑️ Delete", key=f"del_{task.id}", use_container_width=True):
                    task_manager.delete_task(task.id)
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    # Inline edit form, shown below the list when a task is being edited.
    if st.session_state.editing_task_id is not None:
        edit_task = task_manager.get_task(st.session_state.editing_task_id)
        if edit_task is None:
            st.session_state.editing_task_id = None
        else:
            st.markdown("---")
            st.markdown(f"### Editing: {edit_task.title}")
            with st.form("edit_form"):
                e_title = st.text_input("Title", value=edit_task.title)
                e_description = st.text_area("Description", value=edit_task.description)
                ce1, ce2 = st.columns(2)
                with ce1:
                    e_category = st.selectbox(
                        "Category",
                        DEFAULT_CATEGORIES,
                        index=DEFAULT_CATEGORIES.index(edit_task.category)
                        if edit_task.category in DEFAULT_CATEGORIES
                        else 0,
                    )
                with ce2:
                    e_priority = st.selectbox(
                        "Priority", PRIORITY_LEVELS, index=PRIORITY_LEVELS.index(edit_task.priority)
                    )
                e_due_date = st.date_input(
                    "Due date",
                    value=date.fromisoformat(edit_task.due_date) if edit_task.due_date else None,
                )
                save_col, cancel_col = st.columns(2)
                with save_col:
                    save_clicked = st.form_submit_button("💾 Save Changes", use_container_width=True)
                with cancel_col:
                    cancel_clicked = st.form_submit_button("Cancel", use_container_width=True)

                if save_clicked:
                    task_manager.update_task(
                        edit_task.id,
                        title=e_title,
                        description=e_description,
                        category=e_category,
                        priority=e_priority,
                        due_date=e_due_date.isoformat() if e_due_date else None,
                    )
                    st.session_state.editing_task_id = None
                    st.success("Task updated.")
                    st.rerun()
                if cancel_clicked:
                    st.session_state.editing_task_id = None
                    st.rerun()

# ===================== ANALYTICS TAB =====================
with tab_analytics:
    st.markdown("#### 30-Day History")
    history = streak_tracker.get_snapshot_history(limit_days=30)

    if history:
        hist_df = pd.DataFrame([{"Date": s.date, "Completion %": s.completion_pct} for s in history])
        fig = go.Figure()
        fig.add_scatter(
            x=hist_df["Date"],
            y=hist_df["Completion %"],
            mode="lines+markers",
            line=dict(color="#6366F1", width=3),
            fill="tozeroy",
            fillcolor="rgba(99,102,241,0.15)",
        )
        fig.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color=("#F3F4F6" if st.session_state.dark_mode else "#111827"),
            yaxis=dict(range=[0, 100], title="Completion %"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("History will appear here once you've used the tracker for a few days.")

    st.markdown("#### Priority Breakdown")
    if progress.by_priority:
        pr_df = pd.DataFrame(
            [{"Priority": k, "Completed": v["completed"], "Pending": v["pending"]} for k, v in progress.by_priority.items()]
        )
        st.dataframe(pr_df, use_container_width=True, hide_index=True)
    else:
        st.info("No tasks yet.")

    st.markdown("#### Recent Email Activity")
    email_log = get_recent_email_log(limit=10)
    if email_log:
        log_df = pd.DataFrame(email_log)
        log_df["sent_at"] = log_df["sent_at"].apply(format_timestamp_for_display)
        log_df["success"] = log_df["success"].apply(lambda v: "✅ Sent" if v else "❌ Failed")
        st.dataframe(
            log_df[["sent_at", "email_type", "success", "detail"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No emails have been sent yet. They're triggered by the GitHub Actions scheduler.")

# ===================== SETTINGS TAB =====================
with tab_settings:
    st.markdown("#### 📧 Email Configuration Status")
    email_status = validate_email_config()
    if email_status.is_valid:
        st.success("Email is configured correctly via your .env file.")
    else:
        st.warning(
            "Missing email configuration: " + ", ".join(email_status.missing_fields)
            + ". See README.md for setup instructions."
        )
    st.markdown(f"**Scheduled send times (local time):** {', '.join(SCHEDULED_SEND_TIMES)}")
    st.caption(
        "Scheduled emails are sent by a GitHub Actions workflow, independent of whether this "
        "app or your computer is running. See docs/ARCHITECTURE.md for details."
    )

    st.markdown("---")
    st.markdown("#### 🔄 Sync to GitHub")
    st.caption(
        "GitHub Actions only sees tasks that have been pushed to your repository - it can't "
        "see changes made here until they're synced. Click below to commit and push your "
        "latest tasks so the next scheduled email is up to date."
    )

    status = git_sync.get_git_status_summary()
    if status.success:
        st.info(status.message)
    else:
        st.warning(status.message)
    for detail in status.details:
        if detail:
            st.caption(detail)

    if st.button("🔄 Sync latest tasks to GitHub", use_container_width=True, disabled=not status.success):
        with st.spinner("Pushing data/tracker.db to GitHub..."):
            result = git_sync.sync_database_to_github()
        if result.success:
            st.success(result.message)
        else:
            st.error(result.message)
            for detail in result.details:
                if detail:
                    st.code(detail)

    st.markdown("---")
    st.markdown("#### ⬇️ Export Data")
    ce1, ce2 = st.columns(2)
    with ce1:
        csv_tasks = export_service.tasks_to_csv(all_tasks)
        st.download_button(
            "Download Tasks (CSV)",
            data=csv_tasks,
            file_name=f"tasks_{today_iso()}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with ce2:
        csv_history = export_service.snapshots_to_csv(streak_tracker.get_snapshot_history(limit_days=365))
        st.download_button(
            "Download Progress History (CSV)",
            data=csv_history,
            file_name=f"progress_history_{today_iso()}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("#### ℹ️ About")
    st.caption(
        "AI Daily Progress Tracker v1.0.0 - a modular Streamlit app for tracking daily tasks, "
        "with automated email updates powered by GitHub Actions. See README.md for full "
        "documentation."
    )
