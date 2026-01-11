from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.models.xcom_arg import XComArg

from ytmusicrec.pipeline import (
    task_collect_youtube_to_mssql,
    task_score_themes_to_mssql_and_csv,
    task_generate_prompts_to_mssql_and_md,
    task_publish_outputs,
)

LOCAL_TZ = pendulum.timezone("America/New_York")

with DAG(
    dag_id="ytmusicrec_daily",
    description="ytmusicrec: collect YouTube trends -> score themes -> generate AI music prompts -> publish",
    schedule="0 9 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz=LOCAL_TZ),
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "you",
    },
    tags=["ytmusicrec"],
) as dag:

    collect = PythonOperator(
        task_id="collect_youtube_to_mssql",
        python_callable=task_collect_youtube_to_mssql,
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=30),
    )


    collect_out = XComArg(collect)
    run_date = collect_out["run_date"]

    score = PythonOperator(
        task_id="score_themes_to_mssql_and_csv",
        python_callable=task_score_themes_to_mssql_and_csv,
        op_kwargs={"run_date": run_date},
    )

    score_out = XComArg(score)
    top_themes = score_out["top_themes"]

    generate = PythonOperator(
        task_id="generate_prompts_to_mssql_and_md",
        python_callable=task_generate_prompts_to_mssql_and_md,
        op_kwargs={"run_date": run_date, "top_themes": top_themes},
    )

    gen_out = XComArg(generate)

    publish = PythonOperator(
        task_id="publish_outputs",
        python_callable=task_publish_outputs,
        op_kwargs={
            "run_date": run_date,
            "top_themes": top_themes,
            "suno": gen_out["suno"],
            "repo_md_path": gen_out["repo_md_path"],
        },
    )

    collect >> score >> generate >> publish
