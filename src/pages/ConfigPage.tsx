import React, { useCallback, useEffect, useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import {
  Alert,
  Button,
  Field,
  FieldSet,
  Input,
  Select,
  Switch,
  TextArea,
  useStyles2,
} from '@grafana/ui';
import { DEFAULT_SETTINGS, OllyChatSettings } from '../types';

export function ConfigPage() {
  const styles = useStyles2(getStyles);
  const [settings, setSettings] = useState<OllyChatSettings>(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load existing settings from Grafana plugin API
  useEffect(() => {
    fetch('/api/plugins/gopal-ollychat-app/settings')
      .then((r) => r.json())
      .then((data) => {
        if (data.jsonData) {
          setSettings({ ...DEFAULT_SETTINGS, ...data.jsonData });
        }
      })
      .catch(() => {
        // Use defaults if plugin settings API is unavailable
      });
  }, []);

  const handleSave = useCallback(async () => {
    try {
      const resp = await fetch('/api/plugins/gopal-ollychat-app/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: true,
          jsonData: settings,
          pinned: true,
        }),
      });
      if (!resp.ok) {
        throw new Error(`Failed to save: ${resp.statusText}`);
      }
      setSaved(true);
      setError(null);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings');
    }
  }, [settings]);

  const update = <K extends keyof OllyChatSettings>(key: K, value: OllyChatSettings[K]) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className={styles.container}>
      <h3>OllyChat Configuration</h3>

      {saved && <Alert title="Settings saved successfully" severity="success" />}
      {error && <Alert title="Error" severity="error">{error}</Alert>}

      <FieldSet label="Backend Connection">
        <Field label="Orchestrator URL" description="URL of the OllyChat Python orchestrator service">
          <Input
            value={settings.orchestratorUrl}
            onChange={(e) => update('orchestratorUrl', e.currentTarget.value)}
            placeholder="http://localhost:8000"
            width={60}
          />
        </Field>
      </FieldSet>

      <FieldSet label="LLM Configuration">
        <Field label="Default Model" description="Default LLM model for new conversations">
          <Select
            value={settings.defaultModel}
            options={[
              { label: 'Claude Sonnet 4.6', value: 'claude-sonnet-4-6' },
              { label: 'Claude Opus 4.6', value: 'claude-opus-4-6' },
              { label: 'Claude Haiku 4.5', value: 'claude-haiku-4-5' },
              { label: 'GPT-4o', value: 'gpt-4o' },
              { label: 'GPT-4o Mini', value: 'gpt-4o-mini' },
              { label: 'Gemini 2.0 Flash', value: 'gemini-2.0-flash' },
            ]}
            onChange={(v) => v.value && update('defaultModel', v.value)}
            width={40}
          />
        </Field>

        <Field label="Default System Prompt" description="System prompt applied to all new conversations">
          <TextArea
            value={settings.defaultSystemPrompt}
            onChange={(e) => update('defaultSystemPrompt', e.currentTarget.value)}
            rows={8}
          />
        </Field>

        <Field label="Max Tool Loop Iterations" description="Maximum number of tool-use iterations per message (1-16)">
          <Input
            type="number"
            value={settings.maxToolLoopIterations}
            onChange={(e) => update('maxToolLoopIterations', Math.min(16, Math.max(1, parseInt(e.currentTarget.value, 10) || 8)))}
            width={10}
            min={1}
            max={16}
          />
        </Field>
      </FieldSet>

      <FieldSet label="Privacy & Compliance">
        <Field label="Enable PII Detection" description="Scan prompts and responses for personally identifiable information">
          <Switch
            value={settings.enablePII}
            onChange={(e) => update('enablePII', e.currentTarget.checked)}
          />
        </Field>

        {settings.enablePII && (
          <Field label="PII Mode" description="Action when PII is detected">
            <Select
              value={settings.piiMode}
              options={[
                { label: 'Log Only', value: 'log', description: 'Log detection, allow request' },
                { label: 'Redact', value: 'redact', description: 'Replace PII with [REDACTED]' },
                { label: 'Block', value: 'block', description: 'Reject the request entirely' },
                { label: 'Alert', value: 'alert', description: 'Log + trigger Grafana alert' },
              ]}
              onChange={(v) => v.value && update('piiMode', v.value as OllyChatSettings['piiMode'])}
              width={30}
            />
          </Field>
        )}
      </FieldSet>

      <FieldSet label="Cost Tracking">
        <Field label="Enable Cost Tracking" description="Track and display per-message and per-session LLM costs">
          <Switch
            value={settings.enableCostTracking}
            onChange={(e) => update('enableCostTracking', e.currentTarget.checked)}
          />
        </Field>
      </FieldSet>

      <Button variant="primary" onClick={handleSave}>
        Save Settings
      </Button>
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    container: css({
      padding: theme.spacing(3),
      maxWidth: 800,
    }),
  };
}
