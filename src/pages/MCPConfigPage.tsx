import React, { useCallback, useEffect, useState } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import {
  Alert,
  Badge,
  Button,
  Card,
  Field,
  FieldSet,
  IconButton,
  Input,
  Modal,
  Select,
  Switch,
  useStyles2,
} from '@grafana/ui';
import { API } from '../constants';
import { MCPServer } from '../types';

interface AddServerForm {
  name: string;
  url: string;
  transport: 'sse' | 'http';
  authMethod: 'auth-header' | 'none';
  authToken: string;
}

const EMPTY_FORM: AddServerForm = {
  name: '',
  url: '',
  transport: 'sse',
  authMethod: 'none',
  authToken: '',
};

export function MCPConfigPage() {
  const styles = useStyles2(getStyles);
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<AddServerForm>(EMPTY_FORM);
  const [error, setError] = useState<string | null>(null);

  const fetchServers = useCallback(async () => {
    try {
      const r = await fetch(API.MCP_SERVERS);
      const data = await r.json();
      setServers(data.servers ?? []);
    } catch {
      setError('Failed to load MCP servers');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchServers();
  }, [fetchServers]);

  const handleAdd = async () => {
    try {
      await fetch(API.MCP_SERVERS, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name,
          url: form.url,
          transport: form.transport,
          auth_method: form.authMethod,
          auth_token: form.authToken || undefined,
        }),
      });
      setShowAdd(false);
      setForm(EMPTY_FORM);
      fetchServers();
    } catch {
      setError('Failed to add server');
    }
  };

  const handleDelete = async (name: string) => {
    await fetch(`${API.MCP_SERVERS}/${name}`, { method: 'DELETE' });
    fetchServers();
  };

  const handleToggle = async (name: string, enabled: boolean) => {
    await fetch(`${API.MCP_SERVERS}/${name}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
    fetchServers();
  };

  const statusColor: Record<string, 'green' | 'red' | 'orange'> = {
    connected: 'green',
    disconnected: 'orange',
    error: 'red',
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3>MCP Server Connections</h3>
        <Button variant="primary" icon="plus" onClick={() => setShowAdd(true)}>
          Add Server
        </Button>
      </div>

      {error && <Alert title="Error" severity="error">{error}</Alert>}

      <p className={styles.description}>
        Connect to external MCP servers to give the assistant access to tools like GitHub, Jira, PagerDuty, or custom APIs.
        Recommended: 1-5 tools per server, max 16 total.
      </p>

      {loading && <p>Loading servers...</p>}

      <div className={styles.grid}>
        {servers.map((server) => (
          <Card key={server.name} className={styles.card}>
            <Card.Heading>
              {server.name}
              <Badge text={server.status} color={statusColor[server.status] ?? 'orange'} className={styles.badge} />
            </Card.Heading>
            <Card.Meta>
              {server.transport.toUpperCase()} &middot; {server.toolCount} tools &middot; Auth: {server.authMethod}
            </Card.Meta>
            <Card.Description>{server.url}</Card.Description>
            <Card.Actions>
              <Switch
                value={server.enabled}
                onChange={(e) => handleToggle(server.name, e.currentTarget.checked)}
              />
              <IconButton name="trash-alt" tooltip="Remove" onClick={() => handleDelete(server.name)} />
            </Card.Actions>
          </Card>
        ))}

        {!loading && servers.length === 0 && (
          <div className={styles.empty}>
            <p>No MCP servers configured. Add a server to give the assistant access to external tools.</p>
          </div>
        )}
      </div>

      {/* Add Server Modal */}
      <Modal title="Add MCP Server" isOpen={showAdd} onDismiss={() => setShowAdd(false)}>
        <FieldSet>
          <Field label="Server Name" required>
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.currentTarget.value })}
              placeholder="e.g. github, jira, bifrost"
            />
          </Field>
          <Field label="Server URL" required>
            <Input
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.currentTarget.value })}
              placeholder="http://localhost:8765"
            />
          </Field>
          <Field label="Transport">
            <Select
              value={form.transport}
              options={[
                { label: 'SSE', value: 'sse' as const },
                { label: 'HTTP (Streamable)', value: 'http' as const },
              ]}
              onChange={(v) => v.value && setForm({ ...form, transport: v.value })}
            />
          </Field>
          <Field label="Authentication">
            <Select
              value={form.authMethod}
              options={[
                { label: 'None', value: 'none' as const },
                { label: 'Auth Header (Bearer Token)', value: 'auth-header' as const },
              ]}
              onChange={(v) => v.value && setForm({ ...form, authMethod: v.value })}
            />
          </Field>
          {form.authMethod === 'auth-header' && (
            <Field label="Bearer Token">
              <Input
                type="password"
                value={form.authToken}
                onChange={(e) => setForm({ ...form, authToken: e.currentTarget.value })}
                placeholder="glsa_..."
              />
            </Field>
          )}
        </FieldSet>
        <Modal.ButtonRow>
          <Button variant="secondary" onClick={() => setShowAdd(false)}>Cancel</Button>
          <Button variant="primary" onClick={handleAdd} disabled={!form.name || !form.url}>
            Add Server
          </Button>
        </Modal.ButtonRow>
      </Modal>
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  return {
    container: css({ padding: theme.spacing(3), maxWidth: 1000 }),
    header: css({
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: theme.spacing(2),
    }),
    description: css({
      color: theme.colors.text.secondary,
      marginBottom: theme.spacing(3),
    }),
    grid: css({
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))',
      gap: theme.spacing(2),
    }),
    card: css({ position: 'relative' }),
    badge: css({ marginLeft: theme.spacing(1) }),
    empty: css({
      gridColumn: '1 / -1',
      textAlign: 'center',
      padding: theme.spacing(4),
      color: theme.colors.text.secondary,
    }),
  };
}
