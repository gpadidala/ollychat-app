import React from 'react';
import { Route, Switch } from 'react-router-dom';
import { AppRootProps } from '@grafana/data';
import { ChatPage } from './ChatPage';
import { ConfigPage } from './ConfigPage';

export function App(props: AppRootProps) {
  const { basename } = props;

  return (
    <Switch>
      <Route path={`${basename}/config`} component={ConfigPage} />
      <Route path={`${basename}/chat`} component={ChatPage} />
      {/* Default route */}
      <Route component={ChatPage} />
    </Switch>
  );
}
