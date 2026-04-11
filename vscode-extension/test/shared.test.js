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
  resolveTranslatedSuffixAliases,
  resolveTargetSuffix,
} = require('../lib/shared');

test('buildConfigProfiles returns default and provider profiles', () => {
  process.env.TEST_DEEPSEEK_KEY = 'x';
  try {
    const profiles = buildConfigProfiles(
      {
        llm: {
          provider: 'deepseek',
          api_key_env: 'TEST_DEEPSEEK_KEY',
        },
        providers: {
          deepseek: {
            model: 'deepseek-chat',
            api_key_env: 'TEST_DEEPSEEK_KEY',
          },
          openai: {
            model: 'gpt-4.1-mini',
            api_key: 'inline-key',
            base_url: 'https://api.openai.com/v1',
          },
        },
      },
      '/tmp/config.yaml'
    );

    assert.equal(profiles[0].label, '当前默认配置');
    assert.equal(profiles[0].useDefaults, true);
    assert.equal(profiles.length, 2);
    assert.equal(profiles[1].provider, 'openai');
  } finally {
    delete process.env.TEST_DEEPSEEK_KEY;
  }
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
      apiKey: 'inline-key',
    },
  });

  assert.equal(profiles.length, 1);
  assert.equal(profiles[0].label, 'deepseek / deepseek-chat');
  assert.equal(profiles[0].provider, 'deepseek');
  assert.equal(profiles[0].apiKey, 'inline-key');
});

test('buildDirectSettingsProfiles parses direct provider settings', () => {
  process.env.DEEPSEEK_API_KEY = 'x';
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
    inspect(name) {
      if (name === 'deepseek.apiKeyEnv') {
        return { globalValue: values[name] };
      }
      return {};
    },
  };

  try {
    const profiles = buildDirectSettingsProfiles(settings);
    assert.equal(profiles.length, 1);
    assert.equal(profiles[0].label, 'DeepSeek / deepseek-chat');
    assert.equal(profiles[0].provider, 'deepseek');
    assert.equal(profiles[0].apiKeyEnv, 'DEEPSEEK_API_KEY');
    assert.equal(profiles[0].maxTokens, '8192');
  } finally {
    delete process.env.DEEPSEEK_API_KEY;
  }
});

test('buildDirectSettingsProfiles keeps codex profile when auth file is configured', () => {
  const values = {
    'openaiCodex.model': 'gpt-5.4-mini',
    'openaiCodex.baseUrl': 'https://chatgpt.com/backend-api/codex',
    'openaiCodex.authFile': '/tmp/auth.json',
    'openaiCodex.codexHome': '/tmp/.codex',
    'openaiCodex.apiMode': 'responses',
    'openaiCodex.maxTokens': 64000,
  };
  const settings = {
    get(name) {
      return values[name];
    },
    inspect(name) {
      if (name === 'openaiCodex.authFile' || name === 'openaiCodex.codexHome') {
        return { globalValue: values[name] };
      }
      return {};
    },
  };

  const profiles = buildDirectSettingsProfiles(settings);
  assert.equal(profiles.length, 1);
  assert.equal(profiles[0].provider, 'openai-codex');
  assert.equal(profiles[0].authFile, '/tmp/auth.json');
  assert.equal(profiles[0].codexHome, '/tmp/.codex');
});

test('buildConfigProfiles skips provider templates without usable key', () => {
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

  assert.equal(profiles.length, 0);
});

test('buildDirectSettingsProfiles ignores default api key env placeholders', () => {
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
    inspect() {
      return {};
    },
  };

  const profiles = buildDirectSettingsProfiles(settings);
  assert.equal(profiles.length, 0);
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
    'Chinese',
    'zh',
    ['cn', 'chinese'],
    180
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
    '--suffix',
    'zh',
    '--translated-suffix-aliases',
    'cn,chinese',
    '--timeout-sec',
    '180',
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
    'Chinese',
    'zh',
    ['cn', 'chinese'],
    90
  );

  assert.deepEqual(args, [
    'estimate',
    '--json',
    '-i',
    '/tmp/a.md',
    '--language',
    'Chinese',
    '--suffix',
    'zh',
    '--translated-suffix-aliases',
    'cn,chinese',
    '--provider',
    'deepseek',
    '--model',
    'deepseek-chat',
    '--max-tokens',
    '8192',
  ]);
});

test('resolveTranslatedSuffixAliases returns normalized aliases for target language', () => {
  const aliases = resolveTranslatedSuffixAliases(
    {
      Chinese: 'cn, CN; chinese\n_zh',
      Japanese: 'jp',
    },
    'Chinese',
    'zh'
  );

  assert.deepEqual(aliases, ['cn', 'chinese']);
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
    suffix: 'zh',
    chunk_size: 8192,
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
  assert.match(message, /输出后缀: zh/);
  assert.match(message, /chunk_size: 8192/);
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
  assert.match(message, /请先在 VS Code 插件设置里配置模型和 key/);
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

test('resolveCliInstallSpec uses PyPI package name', () => {
  const spec = resolveCliInstallSpec('/tmp/anywhere');
  assert.deepEqual(spec, { packageName: 'mdtomd' });
});

test('resolveTargetLanguage prefers VS Code setting then config default', () => {
  assert.equal(resolveTargetLanguage({ defaults: { language: 'Japanese' } }, 'Chinese'), 'Chinese');
  assert.equal(resolveTargetLanguage({ defaults: { language: 'Japanese' } }, ''), 'Japanese');
  assert.equal(resolveTargetLanguage({}, 'Chinese'), 'Chinese');
});

test('resolveTargetSuffix prefers suffix map then config default', () => {
  assert.equal(resolveTargetSuffix({ defaults: { suffix: 'jp' } }, { Chinese: 'zh' }, 'Chinese'), 'zh');
  assert.equal(resolveTargetSuffix({ defaults: { suffix: 'jp' } }, {}, 'Japanese'), 'ja');
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
  const message = buildStartTranslateMessage(
    '/tmp/a.md',
    'Chinese',
    'zh',
    profile,
    {
      available: true,
      estimated_input_cost: 0.0001,
      estimated_total_cost: 0.0003,
      currency: 'USD',
    },
    {
      chunk_size: 8192,
      summary: {
        file_count: 1,
        pending_file_count: 1,
        skipped_file_count: 0,
        chunk_count: 2,
        source_tokens: 120,
        request_input_tokens: 180,
      },
    }
  );

  assert.match(message, /已选模型: DeepSeek 快/);
  assert.match(message, /输出后缀: zh/);
  assert.match(message, /chunk_size: 8192/);
  assert.match(message, /请求输入 tokens: 180/);
  assert.match(message, /粗估总成本: 0\.000300 USD/);
});
