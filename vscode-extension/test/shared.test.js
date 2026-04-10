const fs = require('fs');
const os = require('os');
const path = require('path');
const test = require('node:test');
const assert = require('node:assert/strict');
const {
  buildCliArgs,
  buildConfigProfiles,
  buildDirectSettingsProfiles,
  buildEstimateMessage,
  buildManualProfile,
  buildSettingsProfiles,
  buildStartTranslateMessage,
  findPriceItem,
  findNearestConfigPath,
  loadConfigFile,
  resolveCliInstallSpec,
  resolveTargetLanguage,
} = require('../lib/shared');

test('buildConfigProfiles returns default and provider profiles', () => {
  const profiles = buildConfigProfiles(
    {
      llm: {
        provider: 'deepseek',
      },
      providers: {
        deepseek: {
          model: 'deepseek-chat',
        },
        openai: {
          model: 'gpt-4.1-mini',
          base_url: 'https://api.openai.com/v1',
        },
      },
    },
    '/tmp/config.yaml'
  );

  assert.equal(profiles[0].label, '当前默认配置');
  assert.equal(profiles[0].useDefaults, true);
  assert.equal(profiles[1].provider, 'deepseek');
  assert.equal(profiles[2].provider, 'openai');
});

test('buildConfigProfiles skips useless auto default without config', () => {
  const profiles = buildConfigProfiles({}, null);
  assert.equal(profiles.length, 0);
});

test('buildSettingsProfiles parses preset profiles from settings', () => {
  const profiles = buildSettingsProfiles({
    deepseek: {
      model: 'deepseek-chat',
      baseUrl: 'https://api.deepseek.com/v1',
      apiKeyEnv: 'DEEPSEEK_API_KEY',
    },
  });

  assert.equal(profiles.length, 1);
  assert.equal(profiles[0].label, 'deepseek / deepseek-chat');
  assert.equal(profiles[0].provider, 'deepseek');
  assert.equal(profiles[0].apiKeyEnv, 'DEEPSEEK_API_KEY');
});

test('buildDirectSettingsProfiles parses direct provider settings', () => {
  const values = {
    'deepseek.model': 'deepseek-chat',
    'deepseek.baseUrl': 'https://api.deepseek.com/v1',
    'deepseek.apiKeyEnv': 'DEEPSEEK_API_KEY',
    'deepseek.apiMode': 'chat_completions',
    'deepseek.maxTokens': 8192,
  };
  const settings = {
    get(name) {
      return values[name];
    },
  };

  const profiles = buildDirectSettingsProfiles(settings);
  assert.equal(profiles.length, 1);
  assert.equal(profiles[0].label, 'DeepSeek / deepseek-chat');
  assert.equal(profiles[0].provider, 'deepseek');
  assert.equal(profiles[0].apiKeyEnv, 'DEEPSEEK_API_KEY');
  assert.equal(profiles[0].maxTokens, '8192');
});

test('buildCliArgs keeps config and explicit profile flags', () => {
  const args = buildCliArgs(
    'translate',
    '/tmp/a.md',
    {
      useDefaults: false,
      provider: 'openai',
      model: 'gpt-4.1-mini',
      baseUrl: 'https://api.openai.com/v1',
      apiKey: 'test-key',
      apiKeyEnv: '',
      codexHome: '/tmp/codex-home',
      authFile: '/tmp/codex-home/auth.json',
      apiMode: 'responses',
      maxTokens: 64000,
    },
    '/tmp/config.yaml',
    'Chinese'
  );

  assert.deepEqual(args, [
    'translate',
    '--json',
    '-i',
    '/tmp/a.md',
    '--config',
    '/tmp/config.yaml',
    '--language',
    'Chinese',
    '--provider',
    'openai',
    '--model',
    'gpt-4.1-mini',
    '--max-tokens',
    '64000',
    '--base-url',
    'https://api.openai.com/v1',
    '--api-key',
    'test-key',
    '--codex-home',
    '/tmp/codex-home',
    '--auth-file',
    '/tmp/codex-home/auth.json',
    '--api-mode',
    'responses',
  ]);
});

test('buildCliArgs does not pass translate-only flags to estimate', () => {
  const args = buildCliArgs(
    'estimate',
    '/tmp/a.md',
    {
      useDefaults: false,
      provider: 'deepseek',
      model: 'deepseek-chat',
      baseUrl: 'https://api.deepseek.com/v1',
      apiKey: 'secret',
      maxTokens: 8192,
    },
    null,
    'Chinese'
  );

  assert.deepEqual(args, [
    'estimate',
    '--json',
    '-i',
    '/tmp/a.md',
    '--language',
    'Chinese',
    '--provider',
    'deepseek',
    '--model',
    'deepseek-chat',
    '--max-tokens',
    '8192',
  ]);
});

test('findNearestConfigPath walks upward to workspace root', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'mdtomd-vscode-'));
  const nestedDir = path.join(tempRoot, 'docs', 'nested');
  fs.mkdirSync(nestedDir, { recursive: true });
  const configPath = path.join(tempRoot, 'config.yaml');
  fs.writeFileSync(configPath, 'llm:\n  provider: deepseek\n', 'utf8');

  assert.equal(findNearestConfigPath(nestedDir, tempRoot), configPath);
});

test('buildEstimateMessage includes core estimate fields', () => {
  const message = buildEstimateMessage('/tmp/a.md', {
    language: 'Chinese',
    provider: 'deepseek',
    model: 'deepseek-chat',
    summary: {
      file_count: 3,
      pending_file_count: 2,
      skipped_file_count: 1,
      chunk_count: 8,
      source_tokens: 900,
      request_input_tokens: 1100,
    },
    pricing: {
      selected_model: {
        available: true,
        estimated_input_cost: 0.001,
        estimated_total_cost: 0.003,
        currency: 'USD',
      },
    },
  });

  assert.match(message, /待翻译文件: 2/);
  assert.match(message, /目标语言: Chinese/);
  assert.match(message, /请求输入 tokens: 1100/);
  assert.match(message, /粗估总成本: 0\.003000 USD/);
});

test('buildEstimateMessage includes featured model prices', () => {
  const message = buildEstimateMessage('/tmp/a.md', {
    language: 'Chinese',
    provider: 'auto',
    model: '-',
    summary: {},
    pricing: {
      featured_models: [
        {
          label: 'OpenAI GPT-4.1 Mini',
          available: true,
          estimated_total_cost: 0.000123,
          currency: 'USD',
        },
      ],
    },
  });

  assert.match(message, /推荐模型价格参考/);
  assert.match(message, /OpenAI GPT-4\.1 Mini \| total≈0\.000123 USD/);
});

test('loadConfigFile parses nested config.yaml', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'mdtomd-vscode-config-'));
  const configPath = path.join(tempRoot, 'config.yaml');
  fs.writeFileSync(
    configPath,
    [
      'llm:',
      '  provider: deepseek',
      'providers:',
      '  deepseek:',
      '    model: deepseek-chat',
      '    api_mode: chat_completions',
      'defaults:',
      '  language: Chinese',
    ].join('\n'),
    'utf8'
  );

  const config = loadConfigFile(configPath);
  assert.equal(config.llm.provider, 'deepseek');
  assert.equal(config.providers.deepseek.model, 'deepseek-chat');
  assert.equal(config.providers.deepseek.api_mode, 'chat_completions');
});

test('resolveCliInstallSpec prefers local repo when pyproject exists', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'mdtomd-vscode-install-'));
  const extensionDir = path.join(tempRoot, 'vscode-extension');
  fs.mkdirSync(path.join(tempRoot, 'mdtomd'), { recursive: true });
  fs.mkdirSync(path.join(tempRoot, 'scripts'), { recursive: true });
  fs.mkdirSync(extensionDir, { recursive: true });
  fs.writeFileSync(path.join(tempRoot, 'pyproject.toml'), '[project]\nname="mdtomd"\n', 'utf8');
  fs.writeFileSync(path.join(tempRoot, 'mdtomd', 'cli.py'), 'def main():\n    return 0\n', 'utf8');
  fs.writeFileSync(path.join(tempRoot, 'scripts', 'install_cli.sh'), '#!/usr/bin/env bash\n', 'utf8');

  const spec = resolveCliInstallSpec(extensionDir);
  assert.equal(spec.editablePath, tempRoot);
  assert.equal(spec.installerPath, path.join(tempRoot, 'scripts', 'install_cli.sh'));
  assert.equal(spec.packageName, 'mdtomd');
});

test('resolveTargetLanguage prefers config defaults then fallback', () => {
  assert.equal(resolveTargetLanguage({ defaults: { language: 'Japanese' } }, 'Chinese'), 'Japanese');
  assert.equal(resolveTargetLanguage({}, 'Chinese'), 'Chinese');
});

test('findPriceItem finds matching featured model', () => {
  const item = findPriceItem(
    {
      pricing: {
        featured_models: [
          {
            provider: 'deepseek',
            model: 'deepseek-chat',
            available: true,
            estimated_total_cost: 0.1,
            currency: 'USD',
          },
        ],
      },
    },
    'deepseek',
    'deepseek-chat'
  );

  assert.equal(item.estimated_total_cost, 0.1);
});

test('buildStartTranslateMessage includes selected model and cost', () => {
  const profile = buildManualProfile();
  profile.label = 'DeepSeek 快';
  profile.provider = 'deepseek';
  profile.model = 'deepseek-chat';
  const message = buildStartTranslateMessage('/tmp/a.md', 'Chinese', profile, {
    available: true,
    estimated_input_cost: 0.0001,
    estimated_total_cost: 0.0003,
    currency: 'USD',
  });

  assert.match(message, /已选模型: DeepSeek 快/);
  assert.match(message, /粗估总成本: 0\.000300 USD/);
});
