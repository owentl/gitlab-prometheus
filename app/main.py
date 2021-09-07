from fastapi import FastAPI, Header, Response
from typing import List
from gitlab.const import GUEST_ACCESS
from retro import run_retro, run_retro2
import gitlab
import requests
import os
import json
from starlette_exporter import PrometheusMiddleware, handle_metrics
from prometheus_client import Counter,Gauge
from starlette.responses import RedirectResponse

app = FastAPI()
app.add_middleware(PrometheusMiddleware)
app.add_route("/metrics", handle_metrics)

gl = gitlab.Gitlab("https://gitlab.com/",private_token=os.environ.get("GL_ACCESS_TOKEN"))
gl.auth()

@app.get("/")
async def read_root():
    return {"Hello": "World"}

@app.get("/retro/coredev/{team}")
async def retro_team(team, iteration: str = None, metric: str = "all"):
    message = await run_retro(team,iteration,"single",metric)
    return json.dumps(message)
    # return {"item_id": int, "iteration": iteration}

@app.get("/retro/coredev/summary/")
async def retro_summary(team, iteration: str = None):
    message = await run_retro(team,iteration,"summary")
    return json.dumps(message)

ISSUE_WEIGHT_FRONTEND = Gauge("gitlabkpis_frontend_Issues_by_weight","Issue Counts by Weight",["team","user"])
ISSUE_WEIGHT_BACKEND = Gauge("gitlabkpis_backend_Issues_by_weight","Issue Counts by Weight",["team","user"])
ISSUE_STATUS = Gauge("gitlabkpis_Issues_by_status","Issue Counts by Status",["status"])
TIME_ESTIMATE = Gauge("gitlabkpis_time_estimate","Time Estimated by User",["team","user"])
TIME_SPENT = Gauge("gitlabkpis_time_spent","Time Spent by User",["team","user"])
TICKETS_USER = Gauge("gitlabkpis_tickets_by_user","Ticket Count by User",["team","user"])
ITERATION_ISSUE_COUNT = Counter("gitlabkpis_iteration_issue_count","Number of issues in the iteration",["iteration","team"])
ITERATION_WEIGHT = Counter("gitlabkpis_iteration_weight","Iteration issues weight",["iteration"])
ITERATION_LABEL_STATUS = Gauge("gitlabkpis_iteration_label_status","Iteration weight by status",["user"])
ITERATION_LABEL_WEIGHT = Gauge("gitlabkpis_iteration_label_weight","Iteration weight by label",["iteration","label"])
ITERATION_TIME_ESTIMATE = Gauge("gitlabkpis_iteration_time_estimate","Time Estimated during Iteration",["iteration"])
ITERATION_TIME_SPENT = Gauge("gitlabkpis_iteration_time_spent","Time Spent during iteration",["iteration"])
ITERATION_TIME_ESTIMATE_LABEL = Gauge("gitlabkpis_iteration_time_estimate_by_status","Time Estimated during Iteration by label",["iteration"])
ITERATION_TIME_SPENT_LABEL = Gauge("gitlabkpis_iteration_time_spent_by_status","Time Spent during iteration by label",["iteration"])


def build_metrics():
    (issue_weights_fe,time_spent_fe,time_estimate_fe,tickets_by_user_fe,issue_status_fe,issue_count_fe,iteration) = run_retro2("frontend","current","single","metrics")

    for user in tickets_by_user_fe:
        TICKETS_USER.labels("frontend",user).set(tickets_by_user_fe[user])
        ITERATION_LABEL_STATUS.labels(user).set(tickets_by_user_fe[user])
    for user in issue_status_fe:
        ISSUE_STATUS.labels(user).set(issue_status_fe[user])
    for user in issue_weights_fe:
        ISSUE_WEIGHT_FRONTEND.labels("frontend",user).set(issue_weights_fe[user])
    for user in time_estimate_fe:
        TIME_ESTIMATE.labels("frontend",user).set(time_estimate_fe[user])
    for user in time_spent_fe:
        TIME_SPENT.labels("frontend",user).set(time_spent_fe[user])
    
    (issue_weights_be,time_spent_be,time_estimate_be,tickets_by_user_be,issue_status_be,issue_count_be,iteration) = run_retro2("backend","current","single","metrics")
    for user in issue_status_be:
        ISSUE_STATUS.labels(user).inc(issue_status_be[user])
    for user in issue_weights_be:
        ISSUE_WEIGHT_BACKEND.labels("backend",user).inc(issue_weights_be[user])
    for user in time_estimate_be:
        TIME_ESTIMATE.labels("backend",user).inc(time_estimate_be[user])
    for user in time_spent_be:
        TIME_SPENT.labels("backend",user).inc(time_spent_be[user])
    for user in tickets_by_user_be:
        TICKETS_USER.labels("backend",user).inc(tickets_by_user_be[user])
        ITERATION_LABEL_STATUS.labels(user).inc(tickets_by_user_fe[user])
    
    ITERATION_ISSUE_COUNT.labels(iteration,"frontend").inc(issue_count_fe)
    ITERATION_ISSUE_COUNT.labels(iteration,"backend").inc(issue_count_be)
    
    (iteration_weight, label_weights,timeestimate,timespent,timesestimate_tally,timespent_tally) = run_retro2("coredev","current","summary","all")
    ITERATION_WEIGHT.labels(iteration).inc(iteration_weight)
    ITERATION_TIME_ESTIMATE.labels(iteration).set(timeestimate)
    ITERATION_TIME_SPENT.labels(iteration).set(timespent)

    for status in timesestimate_tally:
        ITERATION_TIME_ESTIMATE_LABEL.labels(status).set(timesestimate_tally[status])
    for status in timespent_tally:
        ITERATION_TIME_ESTIMATE_LABEL.labels(status).set(timespent_tally[status])
    for label in label_weights:
        ITERATION_LABEL_WEIGHT.labels(iteration,label).set(label_weights[label])
    

build_metrics()
