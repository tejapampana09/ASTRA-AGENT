import { AgentEvent, TranslatedActivity, AgentPhase } from '../types';

export function translateEvent(event: AgentEvent): TranslatedActivity {
  const type = event.event_type || 'UNKNOWN';
  const payload = event.payload || {};
  const msg = event.message || '';
  const seq = event.sequence_id || 0;
  const time = event.timestamp || new Date().toISOString();

  let title = msg;
  let subtitle: string | undefined = undefined;
  let iconType: TranslatedActivity['iconType'] = 'info';
  let phase: AgentPhase = 'EXECUTE';

  switch (type) {
    case 'TASK_CREATED':
    case 'TASK_STARTED':
      title = 'Task initialized';
      subtitle = payload.goal ? `Goal: ${payload.goal}` : msg;
      iconType = 'info';
      phase = 'UNDERSTAND';
      break;

    case 'UNDERSTAND':
      title = 'Task requirements parsed';
      subtitle = payload.goal || msg;
      iconType = 'plan';
      phase = 'UNDERSTAND';
      break;

    case 'WORKSPACE_INITIALIZED':
      title = 'Isolated workspace prepared';
      subtitle = payload.workspace_path || msg;
      iconType = 'info';
      phase = 'REPOSITORY_CONTEXT';
      break;

    case 'REPOSITORY_CONTEXT':
      title = 'Repository structure analyzed';
      if (payload.files_count !== undefined) {
        const langs = (payload.languages || []).join(', ') || 'Python';
        subtitle = `${payload.files_count} files • ${langs} • ${payload.test_framework || 'pytest'}`;
      } else {
        subtitle = msg;
      }
      iconType = 'info';
      phase = 'REPOSITORY_CONTEXT';
      break;

    case 'IMPACT_ANALYSIS':
      title = 'Change impact & blast radius evaluated';
      if (payload.affected_files) {
        subtitle = `${payload.affected_files.length} affected files • Risk: ${payload.risk_level || 'LOW'}`;
      } else {
        subtitle = msg;
      }
      iconType = 'plan';
      phase = 'IMPACT_ANALYSIS';
      break;

    case 'PLANNING':
    case 'PLANNING_STARTED':
      title = 'Intelligent planning in progress';
      subtitle = 'Decomposing task into dependency stages...';
      iconType = 'plan';
      phase = 'PLAN';
      break;

    case 'PLAN_GENERATED':
      title = 'Execution plan formulated';
      subtitle = payload.steps_count ? `${payload.steps_count} dependency stages ready` : msg;
      iconType = 'plan';
      phase = 'PLAN';
      break;

    case 'TOOL_CALL_STARTED': {
      const tool = (payload.tool || payload.tool_name || '').toLowerCase();
      const cmd = payload.command || payload.cmd || '';
      const path = payload.path || '';

      if (tool === 'file_editor' || path) {
        const verb = ['view', 'cat', 'open'].includes(cmd) ? 'Reading' : 'Editing';
        title = `${verb} ${path || 'file'}`;
        subtitle = path;
        iconType = 'file';
      } else if (tool === 'terminal' || cmd) {
        title = `Running ${cmd || 'terminal command'}`;
        subtitle = tool || 'terminal';
        iconType = 'terminal';
      } else {
        title = `Executing ${tool || 'tool'}`;
        subtitle = cmd || path || msg;
        iconType = 'terminal';
      }
      phase = 'EXECUTE';
      break;
    }

    case 'TOOL_CALL_COMPLETED': {
      const tool = (payload.tool || '').toLowerCase();
      const cmd = payload.command || '';
      const summary = payload.summary || '';
      title = `Completed ${cmd ? cmd.slice(0, 40) : (tool || 'tool execution')}`;
      subtitle = summary || (payload.duration_ms ? `${payload.duration_ms}ms` : undefined);
      iconType = payload.exit_code === 0 ? 'terminal' : 'error';
      phase = 'EXECUTE';
      break;
    }

    case 'FILE_CHANGED': {
      const path = payload.path || 'file';
      const op = payload.operation || 'modified';
      title = `${op === 'created' ? 'Created' : 'Modified'} ${path}`;
      subtitle = path;
      iconType = 'file';
      phase = 'EXECUTE';
      break;
    }

    case 'TEST_STARTED': {
      const cmd = payload.command || 'pytest';
      title = `Running ${cmd}`;
      subtitle = 'Executing empirical test suite...';
      iconType = 'terminal';
      phase = 'VERIFY';
      break;
    }

    case 'TEST_COMPLETED': {
      const passed = payload.passed || 0;
      const failed = payload.failed || 0;
      if (failed > 0) {
        title = `Tests failed — ${failed} failed, ${passed} passed`;
        iconType = 'test_fail';
      } else {
        title = `Tests passed — ${passed} passed`;
        iconType = 'test_pass';
      }
      subtitle = payload.command || 'pytest';
      phase = 'VERIFY';
      break;
    }

    case 'DIFF_GENERATED':
      title = 'Git diff generated';
      subtitle = payload.files_changed ? `${payload.files_changed.length} files changed` : msg;
      iconType = 'git';
      phase = 'VERIFY';
      break;

    case 'DEBUG_STARTED':
      title = 'Investigating verification failure';
      subtitle = payload.hypothesis || payload.error || msg;
      iconType = 'debug';
      phase = 'DEBUG';
      break;

    case 'HYPOTHESIS_FORMULATED':
      title = 'Formulated fix hypothesis';
      subtitle = payload.hypothesis || msg;
      iconType = 'debug';
      phase = 'DEBUG';
      break;

    case 'REPLAN_TRIGGERED':
      title = 'Replanning execution';
      subtitle = payload.hypothesis ? `Target: ${payload.target_file || ''} — ${payload.hypothesis}` : msg;
      iconType = 'plan';
      phase = 'REPLAN';
      break;

    case 'APPROVAL_REQUIRED':
      title = 'Human authorization required';
      subtitle = msg;
      iconType = 'approval';
      phase = 'EXECUTE';
      break;

    case 'APPROVAL_GRANTED':
      title = 'Action authorized by reviewer';
      subtitle = msg;
      iconType = 'approval';
      phase = 'EXECUTE';
      break;

    case 'COMMIT_CREATED': {
      const sha = payload.sha ? payload.sha.slice(0, 7) : '';
      title = `Created commit ${sha}`;
      subtitle = payload.message ? payload.message.split('\n')[0] : msg;
      iconType = 'git';
      phase = 'COMMIT';
      break;
    }

    case 'PR_CREATED': {
      const num = payload.pr_number ? `#${payload.pr_number}` : '';
      title = `Pull request created ${num}`;
      subtitle = payload.title || payload.pr_url || msg;
      iconType = 'pr';
      phase = 'PR';
      break;
    }

    case 'TASK_COMPLETED':
      title = 'Task completed & verified';
      subtitle = msg;
      iconType = 'test_pass';
      phase = 'COMPLETED';
      break;

    case 'TASK_FAILED':
    case 'TASK_TIMEOUT':
    case 'TASK_CANCELLED':
      title = type === 'TASK_TIMEOUT' ? 'Task timed out' : (type === 'TASK_CANCELLED' ? 'Task cancelled' : 'Task execution failed');
      subtitle = msg;
      iconType = 'error';
      phase = 'FAILED';
      break;

    default:
      title = msg || type;
      iconType = 'info';
      phase = 'EXECUTE';
      break;
  }

  return {
    title,
    subtitle,
    iconType,
    phase,
    timestamp: time,
    sequence_id: seq,
    rawEvent: event,
  };
}
