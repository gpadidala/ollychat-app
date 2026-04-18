import React, { useEffect, useState } from 'react';
import { Select } from '@grafana/ui';
import { SelectableValue } from '@grafana/data';
import { API } from '../constants';
import { ModelInfo } from '../types';

interface Props {
  value: string;
  onChange: (model: string) => void;
}

export function ModelSelector({ value, onChange }: Props) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    fetch(API.MODELS)
      .then((r) => r.json())
      .then((data: { models: ModelInfo[] }) => {
        if (!cancelled) {
          setModels(data.models ?? []);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          // Fallback to static model list if orchestrator is down
          setModels([
            { id: 'claude-sonnet-4-6', provider: 'anthropic', displayName: 'Claude Sonnet 4.6', contextWindow: 1000000, costPer1kIn: 0.003, costPer1kOut: 0.015, supportsTools: true, supportsStreaming: true, strengths: ['tools', 'long_context'] },
            { id: 'gpt-4o', provider: 'openai', displayName: 'GPT-4o', contextWindow: 128000, costPer1kIn: 0.0025, costPer1kOut: 0.01, supportsTools: true, supportsStreaming: true, strengths: ['reasoning', 'tools'] },
            { id: 'claude-haiku-4-5', provider: 'anthropic', displayName: 'Claude Haiku 4.5', contextWindow: 200000, costPer1kIn: 0.0008, costPer1kOut: 0.004, supportsTools: true, supportsStreaming: true, strengths: ['speed', 'cheap'] },
          ]);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const options: Array<SelectableValue<string>> = models.map((m) => ({
    label: `${m.displayName} (${m.provider})`,
    value: m.id,
    description: `${m.contextWindow.toLocaleString()} ctx | $${m.costPer1kIn}/$${m.costPer1kOut} per 1K tok`,
  }));

  return (
    <Select
      value={value}
      options={options}
      onChange={(v) => v.value && onChange(v.value)}
      isLoading={loading}
      width={35}
      placeholder="Select model..."
    />
  );
}
