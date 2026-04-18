import React from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { Button, Icon, IconButton, useStyles2 } from '@grafana/ui';
import { Conversation } from '../types';

interface Props {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export function ConversationSidebar({ conversations, activeId, onSelect, onNew, onDelete }: Props) {
  const styles = useStyles2(getStyles);

  return (
    <div className={styles.sidebar}>
      <div className={styles.header}>
        <h5 className={styles.title}>Conversations</h5>
        <Button variant="secondary" size="sm" icon="plus" onClick={onNew}>
          New
        </Button>
      </div>
      <div className={styles.list}>
        {conversations.length === 0 && (
          <div className={styles.empty}>
            <Icon name="comment-alt" size="xl" />
            <p>No conversations yet</p>
            <Button variant="primary" size="sm" onClick={onNew}>
              Start chatting
            </Button>
          </div>
        )}
        {conversations.map((conv) => (
          <div
            key={conv.id}
            className={conv.id === activeId ? styles.itemActive : styles.item}
            onClick={() => onSelect(conv.id)}
          >
            <div className={styles.itemContent}>
              <span className={styles.itemTitle}>{conv.title}</span>
              <span className={styles.itemMeta}>
                {conv.messages.length} messages &middot; {conv.model}
              </span>
            </div>
            <IconButton
              name="trash-alt"
              size="sm"
              tooltip="Delete"
              className={styles.deleteBtn}
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function getStyles(theme: GrafanaTheme2) {
  const itemBase = css({
    display: 'flex',
    alignItems: 'center',
    padding: theme.spacing(1, 1.5),
    cursor: 'pointer',
    borderRadius: theme.shape.radius.default,
    marginBottom: 2,
    '&:hover': {
      background: theme.colors.action.hover,
    },
  });

  return {
    sidebar: css({
      width: 260,
      borderRight: `1px solid ${theme.colors.border.weak}`,
      display: 'flex',
      flexDirection: 'column',
      background: theme.colors.background.primary,
      height: '100%',
    }),
    header: css({
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: theme.spacing(2),
      borderBottom: `1px solid ${theme.colors.border.weak}`,
    }),
    title: css({
      margin: 0,
      fontSize: theme.typography.h5.fontSize,
    }),
    list: css({
      flex: 1,
      overflow: 'auto',
      padding: theme.spacing(1),
    }),
    empty: css({
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: theme.spacing(1.5),
      padding: theme.spacing(4, 2),
      color: theme.colors.text.secondary,
      textAlign: 'center',
    }),
    item: itemBase,
    itemActive: css(itemBase, {
      background: theme.colors.action.selected,
      '&:hover': {
        background: theme.colors.action.selected,
      },
    }),
    itemContent: css({
      flex: 1,
      minWidth: 0,
    }),
    itemTitle: css({
      display: 'block',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
      fontWeight: theme.typography.fontWeightMedium,
    }),
    itemMeta: css({
      display: 'block',
      fontSize: theme.typography.bodySmall.fontSize,
      color: theme.colors.text.secondary,
    }),
    deleteBtn: css({
      opacity: 0.5,
      '&:hover': { opacity: 1 },
    }),
  };
}
