# Pipeline Reliability Patterns from Reference Implementations

Research from Temporal, Airflow, Prefect, Dagster, Kestra, and Ray on handling
stuck tasks, heartbeat monitoring, state machines, silent failures, and checkpoint/resume.

---

## 1. Detecting & Handling Stuck/Running Tasks That Never Complete

### Airflow — Zombie Task Detection via Heartbeat Timeout
**File:** `airflow-core/src/airflow/jobs/scheduler_job_runner.py` (lines ~2870-3030)

Airflow's scheduler has a dedicated `_find_and_purge_task_instances_without_heartbeats` loop:
```python
def _find_task_instances_without_heartbeats(self, *, session: Session) -> list[TI]:
    limit_dttm = timezone.utcnow() - timedelta(seconds=self._task_instance_heartbeat_timeout_secs)
    task_instances_without_heartbeats = list(
        session.scalars(
            select(TI)
            .where(
                TI.state.in_((TaskInstanceState.RUNNING, TaskInstanceState.RESTARTING)),
                TI.last_heartbeat_at < limit_dttm,
            )
        )
    )
```
When found, it:
1. Logs a "heartbeat timeout" event
2. Sends a failure callback to the DAG processor
3. Changes state via `executor.change_state(ti.key, TaskInstanceState.FAILED, remove_running=True)`
4. Increments a `task_instances_without_heartbeats_killed` metric

### Airflow — Stuck-in-Queued Task Handling
**File:** `airflow-core/src/airflow/jobs/scheduler_job_runner.py` (lines ~2513-2630)

Tasks stuck in QUEUED state get requeued up to N times before being marked FAILED:
```python
def _handle_tasks_stuck_in_queued(self, session):
    tasks_stuck_in_queued = self._get_tis_stuck_in_queued(session)
    for executor, stuck_tis in self._executor_to_workloads(tasks_stuck_in_queued, session).items():
        for ti in stuck_tis:
            executor.revoke_task(ti=ti)
            self._maybe_requeue_stuck_ti(ti=ti, session=session, executor=executor)

def _maybe_requeue_stuck_ti(self, *, ti, session, executor):
    num_times_stuck = self._get_num_times_stuck_in_queued(ti, session)
    if num_times_stuck < self._num_stuck_queued_retries:
        self._reschedule_stuck_task(ti, session=session)
    else:
        ti.set_state(TaskInstanceState.FAILED, session=session)
        executor.fail(ti.key)
```

**Pattern:** Query for tasks in RUNNING/QUEUED that have exceeded a time threshold → revoke from executor → requeue or fail.

### Dagster — Orphaned Run Detection
**File:** `python_modules/dagster/dagster/_grpc/server.py` (lines ~540-580)

Dagster's gRPC server runs a periodic cleanup thread:
```python
def _check_for_orphaned_runs(self) -> None:
    with self._execution_lock:
        runs_to_clear = []
        for run_id, (process, instance_ref) in self._executions.items():
            if not process.is_alive():
                run = instance.get_run_by_id(run_id)
                if not run or run.is_finished:
                    continue
                message = get_run_crash_explanation(
                    prefix=f"Run execution process for {run.run_id}",
                    exit_code=process.exitcode,
                )
                instance.report_engine_event(message, run, cls=self.__class__)
                instance.report_run_failed(run)
        for run_id in runs_to_clear:
            self._clear_run(run_id)
```

**Pattern:** Periodically scan in-memory map of `{run_id → subprocess}` → check `process.is_alive()` → if dead + run not finished, mark as failed.

### Kestra — Stuck Execution Detection (Concurrency Limit)
**File:** `executor/src/main/java/io/kestra/executor/ConcurrencyLimitStateStore.java`

Kestra explicitly calls out preventing executions from getting "stuck in the queue indefinitely" (issue #13785), and in `DefaultExecutor.java` line 823:
```java
// that could leave executions stuck in the queue indefinitely (see issue #13785)
```

---

## 2. Heartbeat & Timeout Patterns for Long-Running Tasks

### Temporal — Activity Timeout Hierarchy
**File:** `api/matchingservice/v1/request_response.pb.go`

Temporal defines a 4-level timeout hierarchy for activities:
```
ScheduleToCloseTimeout   — total wall-clock time from task creation to completion
ScheduleToStartTimeout   — time waiting in queue before a worker picks it up
StartToCloseTimeout      — max execution time once a worker starts processing
HeartbeatTimeout         — max time between heartbeat pings during execution
```

**File:** `service/worker/scanner/history/scavenger.go`
```go
func (s *Scavenger) heartbeat(ctx context.Context) {
    // Heartbeat to prevent heartbeat timeout.
    s.heartbeat(ctx)
}
```

Activities must call `context.Heartbeat()` periodically. If `HeartbeatTimeout` elapses without a heartbeat, the activity is considered failed and can be retried. The SDK also supports `WorkflowTaskHeartbeatTimeout` for long-running workflow tasks:
```go
// File: service/history/configs/config.go
WorkflowTaskHeartbeatTimeout dynamicconfig.DurationPropertyFnWithNamespaceFilter
```

### Airflow — Task Instance Heartbeats
**File:** `airflow-core/src/airflow/jobs/job.py` (line ~100)

Jobs have a `latest_heartbeat` column:
```python
latest_heartbeat: Mapped[datetime | None] = mapped_column(UtcDateTime())
```

The scheduler loop periodically heartbeats all executors:
```python
# scheduler_job_runner.py ~line 1670
for executor in self.executors:
    executor.heartbeat()
```

The Go SDK worker (`go-sdk/pkg/worker/runner.go`) has a dedicated heartbeater:
```go
type heartbeater struct {
    heartbeatInterval time.Duration
}

func (h *heartbeater) Run(ctx context.Context, ...) {
    ticker := time.NewTicker(h.heartbeatInterval)
    defer ticker.Stop()
    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            err := h.heartbeat(ctx)
            if err != nil {
                // Task cancelled after too many failed heartbeats
            }
        }
    }
}
```

### Kestra — Service Liveness via Periodic Heartbeats
**File:** `core/src/main/java/io/kestra/core/server/ServiceLivenessManager.java`

Kestra's `ServiceLivenessManager` sends periodic state updates (heartbeats):
```java
@Override
protected void onSchedule(final Instant now) {
    serviceRegistry.all().stream()
        .filter(localServiceState -> localServiceState.isStateUpdatable().get())
        .forEach(localServiceState -> {
            ServiceInstance instance = updateServiceInstanceState(now, service, null, callback);
        });
}

@Override
protected Duration getScheduleInterval() {
    return serverConfig.liveness().heartbeatInterval();
}
```

Workers proactively self-disconnect if they fail to update their state before timeout:
```java
// Proactively disconnect a WORKER server when it fails to update its current state
// for more than the configured liveness timeout (this is to prevent zombie server).
if (isLivenessEnabled() && isWorkerServer() && isServerDisconnected(now)) {
    ServiceInstance updated = updateServiceInstanceState(
        now, service, Service.ServiceState.DISCONNECTED, ...
    );
    onStateTransitionFailureCallback.execute(now, service, updated, true);
}
```

### Ray — Replica Health Checks
**File:** `doc/source/serve/doc_code/fault_tolerance/replica_health_check.py`

Ray Serve deployments support configurable health checks:
```python
@serve.deployment(health_check_period_s=10, health_check_timeout_s=30)
class MyDeployment:
    def check_health(self):
        if not self._my_db_connection.is_connected():
            raise RuntimeError("uh-oh, DB connection is broken.")
```

**Pattern:** Periodically call `check_health()` on each replica → if it raises or times out, the replica is marked unhealthy and removed from the routing pool.

---

## 3. Run State Machine Patterns

### Temporal — Workflow Execution State Machine
**File:** `api/enums/v1/workflow.pb.go`
```go
type WorkflowExecutionState int32
const (
    WORKFLOW_EXECUTION_STATE_UNSPECIFIED = 0
    WORKFLOW_EXECUTION_STATE_CREATED     = 1
    WORKFLOW_EXECUTION_STATE_RUNNING     = 2
    WORKFLOW_EXECUTION_STATE_COMPLETED   = 3
    WORKFLOW_EXECUTION_STATE_ZOMBIE      = 4  // ← unique: explicit zombie state
    WORKFLOW_EXECUTION_STATE_VOID        = 5
    WORKFLOW_EXECUTION_STATE_CORRUPTED   = 6
)
```

Zombie workflows are those whose parent workflow completed but the child still has pending work. The system explicitly tracks this state to allow safe cleanup vs. forceful termination.

### Airflow — Task Instance States
**File:** `airflow-core/src/airflow/models/taskinstance.py` (implied from scheduler logic)
```
SCHEDULED → QUEUED → RUNNING → SUCCESS / FAILED
                   ↗ (deferred) DEFERRED → (reschedule) → SCHEDULED
```

DagRun states:
```
QUEUED → RUNNING → SUCCESS / FAILED
```

### Prefect — State Type Enum
**File:** `prefect-main/src/prefect/server/schemas/states.py`
```python
class StateType(AutoEnum):
    PENDING    = AutoEnum.auto()
    RUNNING    = AutoEnum.auto()
    COMPLETED  = AutoEnum.auto()
    FAILED     = AutoEnum.auto()
    CANCELLED  = AutoEnum.auto()
    CRASHED    = AutoEnum.auto()    # ← unique: CRASHED is separate from FAILED
```

Terminal states are: `COMPLETED`, `CANCELLED`, `FAILED`, `CRASHED`

Prefect uses an **orchestration policy pattern** with ordered priority rules:
**File:** `prefect-main/src/prefect/server/orchestration/core_policy.py`
```python
class CoreFlowPolicy(FlowRunOrchestrationPolicy):
    @staticmethod
    def priority() -> list:
        return [
            PreserveDeploymentConcurrencyLeaseId,
            PreventDuplicateTransitions,
            HandleFlowTerminalStateTransitions,
            EnforceCancellingToCancelledTransition,
            BypassCancellingFlowRunsWithNoInfra,
            PreventPendingTransitions,
            ValidateDeploymentConcurrencyAtRunning,
            SecureFlowConcurrencySlots,
            HandlePausingFlows,
            HandleResumingPausedFlows,
            RetryFailedFlows,          # ← auto-retry as part of state machine
            InstrumentFlowRunStateTransitions,
            ReleaseFlowConcurrencySlots,
        ]
```

Each rule is a `before_transition` / `after_transition` hook that can accept, reject, or modify a proposed state change. For example, `RetryFailedFlows` intercepts `RUNNING → FAILED` transitions and converts them to `RUNNING → AWAITING_RETRY` if retries remain.

### Kestra — Execution State Machine
**File:** `core/src/main/java/io/kestra/core/models/flows/State.java`
```java
public enum Type {
    CREATED, SUBMITTED, RUNNING, PAUSED, RESTARTED,
    KILLING, SUCCESS, WARNING, FAILED, KILLED,
    CANCELLED, QUEUED, RETRYING, RETRIED, SKIPPED,
    BREAKPOINT, RESUBMITTED;

    public boolean isTerminated() {
        return this == FAILED || this == WARNING || this == SUCCESS
            || this == KILLED || this == CANCELLED || this == RETRIED
            || this == SKIPPED || this == RESUBMITTED;
    }

    public boolean isRunning() {
        return this == RUNNING || this == KILLING;
    }
}
```

### Kestra — Service State Machine
**File:** `core/src/main/java/io/kestra/core/server/Service.java`
```java
enum ServiceState {
    CREATED(1, 2, 3, 4, 9),           // → RUNNING, ERROR, DISCONNECTED, TERMINATING, MAINTENANCE
    RUNNING(2, 3, 4, 9),              // → ERROR, DISCONNECTED, TERMINATING, MAINTENANCE
    ERROR(4),                          // → TERMINATING
    DISCONNECTED(4, 7),               // → TERMINATING, NOT_RUNNING
    TERMINATING(5, 6, 7),             // → TERMINATED_GRACEFULLY, TERMINATED_FORCED, NOT_RUNNING
    TERMINATED_GRACEFULLY(7),          // → NOT_RUNNING
    TERMINATED_FORCED(7),              // → NOT_RUNNING
    NOT_RUNNING(8),                    // → INACTIVE
    INACTIVE(),                        // FINAL STATE (was called EMPTY)
    MAINTENANCE(1, 2, 3, 4);          // → CREATED, RUNNING, ERROR, DISCONNECTED, TERMINATING

    public boolean isValidTransition(final ServiceState newState) {
        return validTransitions.contains(newState.ordinal()) || equals(newState);
    }
}
```

**Pattern:** Valid transitions are encoded as a static set of ordinals per state. The `isValidTransition()` method is used during state updates to prevent illegal transitions.

---

## 4. Marking Runs as Failed When Background Tasks Die Silently

### Dagster — Process Death Detection
**File:** `python_modules/dagster/dagster/_grpc/server.py`
```python
def _check_for_orphaned_runs(self) -> None:
    for run_id, (process, instance_ref) in self._executions.items():
        if not process.is_alive():
            run = instance.get_run_by_id(run_id)
            if not run or run.is_finished:
                continue
            instance.report_engine_event(message, run, cls=self.__class__)
            instance.report_run_failed(run)
```

Also has an orphan watcher subprocess:
**File:** `python_modules/dagster/dagster/_core/execution/scripts/watch_orphans.py`
```python
def watch(args):
    parent_pid = int(args[0])
    tail_pid = int(args[1])
    while True:
        if os.getppid() != parent_pid:    # parent died → we're orphaned
            os.kill(tail_pid, signal.SIGTERM)
            break
        time.sleep(1)
```

**File:** `python_modules/dagster/dagster/_core/execution/scripts/poll_compute_logs.py`
```python
def current_process_is_orphaned(parent_pid):
    if sys.platform == "win32":
        parent = psutil.Process(parent_pid)
        return parent.status() != psutil.STATUS_RUNNING
    else:
        return os.getppid() != parent_pid
```

**Pattern:** Spawn a watcher subprocess that monitors the parent PID. If parent dies (PPID changes), kill child processes. On the server side, scan for dead subprocesses and mark their runs as failed.

### Airflow — DAG Run Timeout
**File:** `airflow-core/src/airflow/jobs/scheduler_job_runner.py` (lines ~2340-2420)
```python
if (
    dag_run.start_date
    and dag.dagrun_timeout
    and dag_run.start_date < timezone.utcnow() - dag.dagrun_timeout
):
    dag_run.set_state(DagRunState.FAILED)
    for task_instance in unfinished_task_instances:
        task_instance.state = TaskInstanceState.SKIPPED
    callback_to_execute = dag_run.produce_dag_callback(
        dag=dag, success=False, relevant_ti=last_unfinished_ti,
        reason="timed_out",
    )
```

Also handles deferred tasks whose triggers never fire:
```python
def _mark_defERRED_tasks_as_failed(self, ...):
    result = session.execute(
        update(TI).where(
            TI.state == TaskInstanceState.DEFERRED,
            TI.trigger_timeout < timezone.utcnow(),
        ).values(
            state=TaskInstanceState.SCHEDULED,
            next_method=TRIGGER_FAIL_REPR,
            next_kwargs={"error": TriggerFailureReason.TRIGGER_TIMEOUT},
        )
    )
```

### Prefect — Cancellation Cleanup Service
**File:** `prefect-main/src/prefect/server/services/cancellation_cleanup.py`

Prefect runs a perpetual monitor that finds cancelled flow runs and cascades cancellation to children:
```python
@perpetual_service(...)
async def monitor_cancelled_flow_runs(docket, db, ...):
    cancelled_flow_query = (
        sa.select(db.FlowRun.id).where(
            db.FlowRun.state_type == states.StateType.CANCELLED,
            db.FlowRun.end_time.is_not(None),
        )
    )
    for flow_run_id in flow_run_ids:
        await docket.add(cancel_child_task_runs)(flow_run_id)

async def cancel_child_task_runs(flow_run_id, *, db):
    child_task_runs = await models.task_runs.read_task_runs(
        session,
        task_run_filter=filters.TaskRunFilter(
            state=filters.TaskRunFilterState(
                type=filters.TaskRunFilterStateType(any_=NON_TERMINAL_STATES)
            )
        ),
    )
    for task_run in child_task_runs:
        await models.task_runs.set_task_run_state(
            session, task_run_id=task_run.id,
            state=states.Cancelled(message="The parent flow run was cancelled."),
            force=True,
        )
```

Also monitors subflow runs that need cancellation due to parent death.

### Kestra — Worker Death → Task Resubmission
**File:** `executor/src/main/java/io/kestra/executor/DefaultServiceLivenessCoordinator.java`

When a worker is detected as non-responsive:
```java
protected void handleAllNonRespondingServices(Instant now) {
    serviceInstanceRepository.processInstanceInStates(allRunningStates(), (txContext, serviceInstance) -> {
        if (isNonRespondingService(serviceInstance, now)) {
            // Transit to DISCONNECTED
            serviceInstanceRepository.mayTransitServiceTo(
                txContext, serviceInstance, Service.ServiceState.DISCONNECTED, ...
            );
            // Re-emit worker tasks if configured for immediate restart
            if (serviceInstance.config().workerTaskRestartStrategy()
                    .equals(WorkerTaskRestartStrategy.IMMEDIATELY)) {
                reEmitWorkerJobsForWorker(txContext, serviceInstance.uid());
            }
        }
    });
}

protected void handleAllWorkersForUncleanShutdown(Instant now) {
    if (isUncleanShutdownService(serviceInstance, now)) {
        if (serviceInstance.config().workerTaskRestartStrategy().isRestartable()) {
            reEmitWorkerJobsForWorker(txContext, serviceInstance.uid());
        }
        // Transit to NOT_RUNNING
        serviceInstanceRepository.mayTransitServiceTo(
            txContext, serviceInstance, Service.ServiceState.NOT_RUNNING, ...
        );
    }
}
```

The `reEmitWorkerJobsForWorker` method re-submits all tasks that were running on the dead worker, using `WorkerJobRunningStateStore` to track in-flight work:
```java
private void reEmitWorkerJobsForWorker(TransactionContext txContext, String id) {
    workerJobRunningStateStore.processWorkerJobsForDeadWorker(txContext, id, (txContext2, workerJobRunning) -> {
        resubmitWorkerJobRunning(txContext2, workerJobRunning);
    });
}
```

---

## 5. Checkpoint & Resume Patterns

### Ray — Lineage-Based Object Reconstruction
**File:** `python/ray/_private/worker.py` (lines ~1566-1571)

Ray supports automatic object reconstruction via lineage:
```python
_enable_object_reconstruction: If True, when an object stored in
    the distributed memory store is lost, Ray will attempt to
    reconstruct the object by re-executing the task that
    created it.
```

When objects are lost (e.g., node failure), Ray uses its lineage graph to replay the tasks that created those objects. This is a form of implicit checkpointing — the lineage metadata acts as a recipe for reconstruction.

**File:** `python/ray/util/state/common.py`
```python
num_restarts_due_to_lineage_reconstruction: int = state_column(...)
```

### Ray — Actor Reconstruction
**File:** `doc/source/ray-core/doc_code/actor_restart.py`
```python
# The actor will be reconstructed up to 4 times, so we can execute up to 50
# tasks successfully. The actor is reconstructed by rerunning its constructor.
```

When an actor dies, Ray automatically reruns its constructor (up to `max_restarts` times) and re-submits pending tasks.

### Dagster — Watcher Process for Orphaned Log Tail
**File:** `python_modules/dagster/dagster/_core/execution/compute_logs.py`

Dagster spawns a watcher process alongside each computation to ensure log tail processes don't become orphaned:
```python
# open a watcher process to check for the orphaning of the tail process
watcher_file = os.path.abspath(watch_orphans.__file__)
```

### Kestra — Worker Job Running State Store (Checkpoint)
**File:** `executor/src/main/java/io/kestra/executor/DefaultServiceLivenessCoordinator.java`

Kestra maintains a `WorkerJobRunningStateStore` that tracks all in-flight worker jobs. When a worker dies, this store is used to find and resubmit those jobs:
```java
workerJobRunningStateStore.processWorkerJobsForDeadWorker(txContext, id, (txContext2, workerJobRunning) -> {
    resubmitWorkerJobRunning(txContext2, workerJobRunning);
});
```

This is effectively a checkpoint — the running state store persists which tasks are in-flight, enabling recovery.

### Temporal — Event Sourcing as Implicit Checkpoint
Temporal uses event sourcing: every state change is an immutable event persisted to the history store. Workflows can be reconstructed by replaying these events. The `WorkflowExecutionState` machine (CREATED → RUNNING → COMPLETED/ZOMBIE) combined with the full event history allows any workflow to be resumed from any point.

The `WORKFLOW_EXECUTION_STATE_ZOMBIE` state specifically handles the case where a parent workflow completed but child workflows still have pending work — the zombie state allows the system to track and clean up these orphans.

---

## Summary Table: Pattern Cross-Reference

| Pattern | Airflow | Prefect | Dagster | Temporal | Kestra | Ray |
|---------|---------|---------|---------|----------|--------|-----|
| **Stuck task detection** | Heartbeat timeout query | Cancellation cleanup monitor | Process liveness check | Activity heartbeat timeout | Service liveness coordinator | Health check period |
| **Heartbeat mechanism** | `last_heartbeat_at` column + scheduler loop | (Not server-side) | Process alive check | `HeartbeatTimeout` + SDK heartbeat calls | `ServiceLivenessManager.onSchedule()` | `health_check_period_s` |
| **State machine** | TaskInstanceState enum + DB transitions | `StateType` enum + orchestration policies | DagsterRunStatus | `WorkflowExecutionState` enum | `State.Type` + `ServiceState` enum | Actor states |
| **Silent failure detection** | Heartbeat timeout + DAG run timeout | Cancellation cleanup (find-and-flood) | Orphaned run check thread | Heartbeat timeout + workflow timeout | Liveness coordinator + job state store | Lineage reconstruction |
| **Checkpoint/resume** | Task retries + requeue | Retry policies + state orchestration | Watcher subprocess | Event sourcing replay | `WorkerJobRunningStateStore` resubmit | Lineage-based object reconstruction |
