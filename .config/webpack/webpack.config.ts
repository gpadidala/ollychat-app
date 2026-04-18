import type { Configuration } from 'webpack';
import { merge } from 'webpack-merge';
import path from 'path';
import CopyWebpackPlugin from 'copy-webpack-plugin';

const config = async (env: Record<string, unknown>): Promise<Configuration> => {
  const baseConfig: Configuration = {
    context: path.resolve(__dirname, '../..'),
    entry: './src/module.ts',
    output: {
      path: path.resolve(__dirname, '../../dist'),
      filename: 'module.js',
      library: { type: 'amd' },
      publicPath: '/',
      clean: true,
    },
    externals: [
      'react',
      'react-dom',
      'react-router-dom',
      '@grafana/ui',
      '@grafana/data',
      '@grafana/runtime',
      'emotion',
      '@emotion/css',
      '@emotion/react',
    ],
    resolve: {
      extensions: ['.ts', '.tsx', '.js', '.jsx'],
    },
    module: {
      rules: [
        {
          test: /\.[tj]sx?$/,
          exclude: /node_modules/,
          use: {
            loader: 'swc-loader',
            options: {
              jsc: {
                parser: { syntax: 'typescript', tsx: true },
                transform: { react: { runtime: 'automatic' } },
                target: 'es2021',
              },
            },
          },
        },
        {
          test: /\.css$/,
          use: ['style-loader', 'css-loader'],
        },
      ],
    },
    plugins: [
      new CopyWebpackPlugin({
        patterns: [
          { from: 'src/plugin.json', to: '.' },
          { from: 'src/img', to: 'img', noErrorOnMissing: true },
        ],
      }),
    ],
  };

  if (env.production) {
    return merge(baseConfig, { mode: 'production', devtool: 'source-map' });
  }

  return merge(baseConfig, {
    mode: 'development',
    devtool: 'eval-source-map',
    watchOptions: { ignored: /node_modules/ },
  });
};

export default config;
