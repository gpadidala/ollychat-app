import React, { useCallback, useEffect, useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import {
  Badge,
  Button,
  Card,
  Field,
  FieldSet,
  Input,
  Modal,
  Select,
  Switch,
  TextArea,
  IconButton,
  useStyles2,
} from '@grafana/ui';
import { API } from '../constants';
import { Rule } from '../types';

export function RulesPage() {
  const styles = useStyles2(getStyles);
  const [rules, setRules] = useState<Rule[]>([]);
  const [showEditor, setShowEditor] = useState(false);
  const [editing, setEditing] = useState<Rule | null>(null);
  const [form, setForm] = useState<Partial<Rule>>({});

  const fetchRules = useCallback(async () => {
    try {
      const r = await fetch(API.RULES);
      const data = await r.json();
      setRules(data.rules ?? []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchRules(); }, [fetchRules]);

  const openEditor = (rule?: Rule) => {
    setEditing(rule ?? null);
    setForm(rule ?? { name: '', content: '', scope: 'just-me', enabled: true, applications: ['assistant'] });
    setShowEditor(true);
  };

  const saveRule = async () => {
    const method = editing ? 'PUT' : 'POST';
    const url = editing ? `${API.RULES}/${editing.id}` : API.RULES;
    await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
    setShowEditor(false);
    fetchRules();
  };

  const deleteRule = async (id: string) => {
    await fetch(`${API.RULES}/${id}`, { method: 'DELETE' });
    fetchRules();
  };

  const toggleRule = async (id: string, enabled: boolean) => {
    await fetch(`${API.RULES}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    fetchRules();
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>Rules</h3>
        <Button variant="primary" icon="plus" onClick={() => openEditor()}>New Rule</Button>
      </div>

      <p className={styles.description}>
        Rules are behavioral guidelines automatically applied to every conversation.
        They strongly influence how the assistant responds, recommends, and troubleshoots.
      </p>

      <div className={styles.list}>
        {rules.map((rule) => (
          <div key={rule.id} className={styles.ruleItem}>
            <Switch value={rule.enabled} onChange={(e) => toggleRule(rule.id, e.currentTarget.checked)} />
            <div className={styles.ruleContent}>
              <div className={styles.ruleName}>
                {rule.name}
                <Badge text={rule.scope} color={rule.scope === 'everybody' ? 'blue' : 'purple'} />
                {rule.applications.map((a) => <Badge key={a} text={a} color="green" />)}
              </div>
              <div className={styles.rulePreview}>
                {rule.content.slice(0, 200)}{rule.content.length > 200 ? '...' : ''}
              </div>
            </div>
            <div className={styles.ruleActions}>
              <IconButton name="pen" tooltip="Edit" onClick={() => openEditor(rule)} />
              <IconButton name="trash-alt" tooltip="Delete" onClick={() => deleteRule(rule.id)} />
            </div>
          </div>
        ))}
        {rules.length === 0 && (
          <p className={styles.empty}>No rules configured. Create rules to guide the assistant's behavior.</p>
        )}
      </div>

      <Modal title={editing ? 'Edit Rule' : 'New Rule'} isOpen={showEditor} onDismiss={() => setShowEditor(false)}>
        <FieldSet>
          <Field label="Name" required>
            <Input value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.currentTarget.value })} />
          </Field>
          <Field label="Content" description="Natural language instructions for the assistant" required>
            <TextArea value={form.content ?? ''} onChange={(e) => setForm({ ...form, content: e.currentTarget.value })} rows={10} />
          </Field>
          <Field label="Scope">
            <Select value={form.scope ?? 'just-me'}
              options={[
                { label: 'Just Me', value: 'just-me' },
                { label: 'Everybody (requires Admin)', value: 'everybody' },
              ]}
              onChange={(v) => v.value && setForm({ ...form, scope: v.value as 'just-me' | 'everybody' })} />
          </Field>
          <Field label="Enabled">
            <Switch value={form.enabled ?? true} onChange={(e) => setForm({ ...form, enabled: e.currentTarget.checked })} />
          </Field>
        </FieldSet>
        <Modal.ButtonRow>
          <Button variant="secondary" onClick={() => setShowEditor(false)}>Cancel</Button>
          <Button variant="primary" onClick={saveRule} disabled={!form.name || !form.content}>Save</Button>
        </Modal.ButtonRow>
      </Modal>
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    container: css({ padding: theme.spacing(3), maxWidth: 900 }),
    header: css({ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing(2) }),
    description: css({ color: theme.colors.text.secondary, marginBottom: theme.spacing(3) }),
    list: css({}),
    ruleItem: css({
      display: 'flex', alignItems: 'flex-start', gap: theme.spacing(2),
      padding: theme.spacing(2), borderBottom: `1px solid ${theme.colors.border.weak}`,
      '&:hover': { background: theme.colors.action.hover },
    }),
    ruleContent: css({ flex: 1 }),
    ruleName: css({
      display: 'flex', alignItems: 'center', gap: theme.spacing(1),
      fontWeight: theme.typography.fontWeightMedium, marginBottom: theme.spacing(0.5),
    }),
    rulePreview: css({
      fontSize: theme.typography.bodySmall.fontSize, color: theme.colors.text.secondary,
      fontFamily: theme.typography.fontFamilyMonospace,
    }),
    ruleActions: css({ display: 'flex', gap: theme.spacing(0.5) }),
    empty: css({ color: theme.colors.text.secondary, fontStyle: 'italic', textAlign: 'center', padding: theme.spacing(4) }),
  };
}
