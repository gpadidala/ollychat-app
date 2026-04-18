import React, { useCallback, useEffect, useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import {
  Badge,
  Button,
  Card,
  Field,
  FieldSet,
  FilterInput,
  Icon,
  IconButton,
  Modal,
  Select,
  TextArea,
  Input,
  useStyles2,
} from '@grafana/ui';
import { API } from '../constants';
import { Skill } from '../types';

export function SkillsPage() {
  const styles = useStyles2(getStyles);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [search, setSearch] = useState('');
  const [showEditor, setShowEditor] = useState(false);
  const [editing, setEditing] = useState<Skill | null>(null);
  const [form, setForm] = useState<Partial<Skill>>({});

  const fetchSkills = useCallback(async () => {
    try {
      const r = await fetch(API.SKILLS);
      const data = await r.json();
      setSkills(data.skills ?? []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchSkills(); }, [fetchSkills]);

  const filtered = skills.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.description.toLowerCase().includes(search.toLowerCase()) ||
    s.tags.some((t) => t.toLowerCase().includes(search.toLowerCase()))
  );

  const openEditor = (skill?: Skill) => {
    setEditing(skill ?? null);
    setForm(skill ?? {
      name: '', description: '', category: 'general', systemPrompt: '',
      toolWhitelist: [], tags: [], visibility: 'just-me', slashCommand: '',
    });
    setShowEditor(true);
  };

  const saveSkill = async () => {
    const method = editing ? 'PUT' : 'POST';
    const url = editing ? `${API.SKILLS}/${editing.id}` : API.SKILLS;
    await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    });
    setShowEditor(false);
    fetchSkills();
  };

  const deleteSkill = async (id: string) => {
    await fetch(`${API.SKILLS}/${id}`, { method: 'DELETE' });
    fetchSkills();
  };

  const CATEGORIES = [
    { label: 'General', value: 'general' },
    { label: 'Incident Triage', value: 'incident-triage' },
    { label: 'Health Check', value: 'health-check' },
    { label: 'Infrastructure', value: 'infrastructure' },
    { label: 'Database', value: 'database' },
    { label: 'Deployment', value: 'deployment' },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>Skills</h3>
        <Button variant="primary" icon="plus" onClick={() => openEditor()}>New Skill</Button>
      </div>

      <p className={styles.description}>
        Skills are reusable guides that help the assistant troubleshoot services, handle alerts, and manage infrastructure.
        They are discovered via semantic search at runtime based on the user's prompt.
      </p>

      <FilterInput value={search} onChange={setSearch} placeholder="Search skills..." />

      <div className={styles.grid}>
        {filtered.map((skill) => (
          <Card key={skill.id} className={styles.card}>
            <Card.Heading>{skill.name}</Card.Heading>
            <Card.Meta>
              {skill.category} &middot; {skill.visibility}
              {skill.slashCommand && <> &middot; <code>/{skill.slashCommand}</code></>}
            </Card.Meta>
            <Card.Description>{skill.description}</Card.Description>
            <Card.Tags>
              {skill.tags.map((t) => <Badge key={t} text={t} color="blue" />)}
            </Card.Tags>
            <Card.Actions>
              <IconButton name="pen" tooltip="Edit" onClick={() => openEditor(skill)} />
              <IconButton name="trash-alt" tooltip="Delete" onClick={() => deleteSkill(skill.id)} />
            </Card.Actions>
          </Card>
        ))}
      </div>

      {/* Editor Modal */}
      <Modal title={editing ? 'Edit Skill' : 'New Skill'} isOpen={showEditor} onDismiss={() => setShowEditor(false)}>
        <FieldSet>
          <Field label="Name" required>
            <Input value={form.name ?? ''} onChange={(e) => setForm({ ...form, name: e.currentTarget.value })} />
          </Field>
          <Field label="Description">
            <Input value={form.description ?? ''} onChange={(e) => setForm({ ...form, description: e.currentTarget.value })} />
          </Field>
          <Field label="Category">
            <Select value={form.category} options={CATEGORIES}
              onChange={(v) => v.value && setForm({ ...form, category: v.value })} />
          </Field>
          <Field label="Slash Command" description="Optional, e.g. triage (without /)">
            <Input value={form.slashCommand ?? ''} onChange={(e) => setForm({ ...form, slashCommand: e.currentTarget.value })}
              placeholder="triage" />
          </Field>
          <Field label="System Prompt" description="Instructions for the assistant when this skill is active">
            <TextArea value={form.systemPrompt ?? ''} onChange={(e) => setForm({ ...form, systemPrompt: e.currentTarget.value })}
              rows={12} />
          </Field>
          <Field label="Tags" description="Comma-separated">
            <Input value={form.tags?.join(', ') ?? ''} onChange={(e) => setForm({ ...form, tags: e.currentTarget.value.split(',').map((t) => t.trim()).filter(Boolean) })} />
          </Field>
          <Field label="Visibility">
            <Select value={form.visibility ?? 'just-me'}
              options={[
                { label: 'Just Me', value: 'just-me' },
                { label: 'Everybody', value: 'everybody' },
              ]}
              onChange={(v) => v.value && setForm({ ...form, visibility: v.value as 'just-me' | 'everybody' })} />
          </Field>
        </FieldSet>
        <Modal.ButtonRow>
          <Button variant="secondary" onClick={() => setShowEditor(false)}>Cancel</Button>
          <Button variant="primary" onClick={saveSkill} disabled={!form.name}>Save</Button>
        </Modal.ButtonRow>
      </Modal>
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    container: css({ padding: theme.spacing(3), maxWidth: 1200 }),
    header: css({ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: theme.spacing(2) }),
    description: css({ color: theme.colors.text.secondary, marginBottom: theme.spacing(2) }),
    grid: css({
      display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
      gap: theme.spacing(2), marginTop: theme.spacing(2),
    }),
    card: css({}),
  };
}
