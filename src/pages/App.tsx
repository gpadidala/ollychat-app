import React from 'react';
import { Route, Switch } from 'react-router-dom';
import { AppRootProps } from '@grafana/data';
import { ChatPage } from './ChatPage';
import { ConfigPage } from './ConfigPage';
import { MCPConfigPage } from './MCPConfigPage';
import { InvestigatePage } from './InvestigatePage';
import { SkillsPage } from './SkillsPage';
import { RulesPage } from './RulesPage';

export function App(props: AppRootProps) {
  const { basename } = props;

  return (
    <Switch>
      <Route path={`${basename}/config`} component={ConfigPage} />
      <Route path={`${basename}/mcp`} component={MCPConfigPage} />
      <Route path={`${basename}/investigate`} component={InvestigatePage} />
      <Route path={`${basename}/skills`} component={SkillsPage} />
      <Route path={`${basename}/rules`} component={RulesPage} />
      <Route path={`${basename}/chat`} component={ChatPage} />
      {/* Default route */}
      <Route component={ChatPage} />
    </Switch>
  );
}
