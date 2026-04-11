const fs = require('fs');
const os = require('os');
const path = require('path');
const { loadSimpleYaml } = require('./simpleYaml');

const CONFIG_NAMES = ['config.yaml', 'config.yml'];
const SUPPORTED_EXTENSIONS = new Set(['.md', '.markdown', '.mdx']);
const DIRECT_PROVIDER_DEFINITIONS = [
  { key: 'deepseek', provider: 'deepseek', label: 'DeepSeek' },
  { key: 'minimax', provider: 'minimax', label: 'MiniMax' },
  { key: 'openai', provider: 'openai', label: 'OpenAI' },
  { key: 'openaiCodex', provider: 'openai-codex', label: 'OpenAI Codex' },
  { key: 'openrouter', provider: 'openrouter', label: 'OpenRouter' },
  { key: 'anthropic', provider: 'anthropic', label: 'Anthropic' },
  { key: 'gemini', provider: 'gemini', label: 'Gemini' },
  { key: 'zai', provider: 'zai', label: 'Z.ai' },
  { key: 'kimi', provider: 'kimi', label: 'Kimi' },
  { key: 'alibaba', provider: 'alibaba', label: 'Alibaba' },
  { key: 'openaiCompatible', provider: 'openai-compatible', label: 'OpenAI Compatible' },
];
const DEFAULT_LANGUAGE_SUFFIXES = {
  Spanish: 'es',
  French: 'fr',
  German: 'de',
  Italian: 'it',
  Portuguese: 'pt',
  Dutch: 'nl',
  Russian: 'ru',
  Chinese: 'zh',
  Japanese: 'ja',
  Korean: 'ko',
  Arabic: 'ar',
  Hindi: 'hi',
  Turkish: 'tr',
  Polish: 'pl',
  Swedish: 'sv',
  Norwegian: 'no',
  Danish: 'da',
  Finnish: 'fi',
  Greek: 'el',
  Hebrew: 'he',
  Thai: 'th',
  Vietnamese: 'vi',
  Indonesian: 'id',
  Malay: 'ms',
  Ukrainian: 'uk',
  Czech: 'cs',
  Hungarian: 'hu',
  Romanian: 'ro',
  Bulgarian: 'bg',
  Croatian: 'hr',
  Serbian: 'sr',
  Slovak: 'sk',
  Slovenian: 'sl',
  Estonian: 'et',
  Latvian: 'lv',
  Lithuanian: 'lt',
  Catalan: 'ca',
  Basque: 'eu',
  Welsh: 'cy',
  Irish: 'ga',
};

function isMarkdownPath(filePath) {
  return SUPPORTED_EXTENSIONS.has(path.extname(filePath).toLowerCase());
}

function findNearestConfigPath(startDir, workspaceRoot) {
  const initialDir = path.resolve(startDir);
  const stopDir = workspaceRoot ? path.resolve(workspaceRoot) : null;
  let currentDir = initialDir;

  while (true) {
    for (const name of CONFIG_NAMES) {
      const candidate = path.join(currentDir, name);
      if (fs.existsSync(candidate)) {
        return candidate;
      }
    }

    if (stopDir && currentDir === stopDir) {
      return null;
    }

    const parentDir = path.dirname(currentDir);
    if (parentDir === currentDir) {
      return null;
    }
    currentDir = parentDir;
  }
}

function loadConfigFile(configPath) {
  return loadSimpleYaml(fs.readFileSync(configPath, 'utf8'));
}

function resolveCliInstallSpec() {
  return {
    packageName: 'mdtomd',
  };
}

function buildConfigProfiles(rawConfig, configPath) {
  const llm = asObject(rawConfig.llm);
  const providers = asObject(rawConfig.providers);
  const defaultProvider = readString(llm.provider) || 'auto';
  const defaultOverride = asObject(providers[defaultProvider]);
  const defaultModel = readString(llm.model) || readString(defaultOverride.model) || '-';

  const profiles = [];
  const defaultProfile = {
      id: 'default',
      label: '当前默认配置',
      description: `${defaultProvider} / ${defaultModel}`,
      detail: configPath ? path.basename(configPath) : '使用 CLI 当前默认解析',
      useDefaults: true,
      provider: defaultProvider,
      model: defaultModel === '-' ? '' : defaultModel,
      apiKey: readString(llm.api_key) || readString(defaultOverride.api_key),
      apiKeyEnv: readString(llm.api_key_env) || readString(defaultOverride.api_key_env),
      codexHome: readString(llm.codex_home) || readString(defaultOverride.codex_home),
      authFile: readString(llm.auth_file) || readString(defaultOverride.auth_file),
      source: 'config-default',
    };
  const hasUsefulDefault = Boolean(configPath || defaultProvider !== 'auto' || defaultModel !== '-');
  if (hasUsefulDefault && isUsableProfile(defaultProfile)) {
    profiles.push(defaultProfile);
  }

  for (const [provider, value] of Object.entries(providers)) {
    const override = asObject(value);
    const hasUsefulValue = ['model', 'base_url', 'api_key', 'api_key_env', 'api_mode', 'codex_home', 'auth_file'].some((key) => readString(override[key]));
    if (!hasUsefulValue) {
      continue;
    }

    const profile = {
      id: `provider:${provider}`,
      label: `${provider} / ${readString(override.model) || '-'}`,
      description: 'config.providers',
      detail: buildProviderDetail(override),
      useDefaults: false,
      provider,
      model: readString(override.model),
      baseUrl: readString(override.base_url),
      apiKey: readString(override.api_key),
      apiKeyEnv: readString(override.api_key_env),
      codexHome: readString(override.codex_home),
      authFile: readString(override.auth_file),
      apiMode: readString(override.api_mode),
      source: 'config-provider',
    };
    const isDuplicateDefault = profiles.some(
      (item) =>
        item.source === 'config-default'
        && readString(item.provider) === readString(profile.provider)
        && readString(item.model) === readString(profile.model)
    );
    if (isUsableProfile(profile) && !isDuplicateDefault) {
      profiles.push(profile);
    }
  }

  return profiles;
}

function buildSettingsProfiles(rawProfiles) {
  if (!isPlainObject(rawProfiles)) {
    return [];
  }

  const profiles = [];
  for (const [providerName, value] of Object.entries(rawProfiles)) {
    const item = asObject(value);
    const provider = readString(providerName);
    const model = readString(item.model);
    const profile = {
      id: `settings:${provider}`,
      label: `${provider} / ${model}`,
      description: `${provider} / ${model}`,
      detail: buildProviderDetail({
        base_url: item.baseUrl ?? item.base_url,
        api_key_env: item.apiKeyEnv ?? item.api_key_env,
        api_mode: item.apiMode ?? item.api_mode,
        codex_home: item.codexHome ?? item.codex_home,
        auth_file: item.authFile ?? item.auth_file,
        max_tokens: item.maxTokens ?? item.max_tokens,
      }),
      useDefaults: false,
      provider,
      model,
      baseUrl: readString(item.baseUrl ?? item.base_url),
      apiKey: readString(item.apiKey ?? item.api_key),
      apiKeyEnv: readString(item.apiKeyEnv ?? item.api_key_env),
      codexHome: readString(item.codexHome ?? item.codex_home),
      authFile: readString(item.authFile ?? item.auth_file),
      apiMode: readString(item.apiMode ?? item.api_mode),
      maxTokens: readString(item.maxTokens ?? item.max_tokens),
      source: 'settings',
    };
    if (!provider || !model || !isUsableProfile(profile)) {
      continue;
    }

    profiles.push(profile);
  }
  return profiles;
}

function buildDirectSettingsProfiles(settings) {
  const profiles = [];
  for (const definition of DIRECT_PROVIDER_DEFINITIONS) {
    const model = readString(settings.get(`${definition.key}.model`));
    if (!model) {
      continue;
    }

    const profile = {
      id: `direct:${definition.key}`,
      label: `${definition.label} / ${model}`,
      description: `${definition.provider} / ${model}`,
      detail: buildProviderDetail({
        base_url: settings.get(`${definition.key}.baseUrl`),
        api_key_env: getConfiguredSetting(settings, `${definition.key}.apiKeyEnv`),
        api_mode: settings.get(`${definition.key}.apiMode`),
        codex_home: settings.get(`${definition.key}.codexHome`),
        auth_file: settings.get(`${definition.key}.authFile`),
        max_tokens: settings.get(`${definition.key}.maxTokens`),
      }),
      useDefaults: false,
      provider: definition.provider,
      model,
      baseUrl: readString(settings.get(`${definition.key}.baseUrl`)),
      apiKey: getConfiguredSetting(settings, `${definition.key}.apiKey`),
      apiKeyEnv: getConfiguredSetting(settings, `${definition.key}.apiKeyEnv`),
      codexHome: getConfiguredSetting(settings, `${definition.key}.codexHome`),
      authFile: getConfiguredSetting(settings, `${definition.key}.authFile`),
      apiMode: readString(settings.get(`${definition.key}.apiMode`)),
      maxTokens: readString(settings.get(`${definition.key}.maxTokens`)),
      source: 'settings-direct',
    };
    if (isUsableProfile(profile)) {
      profiles.push(profile);
    }
  }
  return profiles;
}

function buildManualProfile() {
  return {
    id: 'manual',
    label: '临时输入模型配置',
    description: '手动填写 provider / model / api_key / base_url',
    detail: '',
    isManual: true,
    useDefaults: false,
    source: 'manual',
  };
}

function resolveTargetLanguage(rawConfig, fallbackLanguage) {
  const defaults = asObject(rawConfig.defaults);
  return readString(fallbackLanguage) || readString(defaults.language) || 'Chinese';
}

function resolveTargetSuffix(rawConfig, rawSuffixMap, targetLanguage) {
  const defaults = asObject(rawConfig.defaults);
  const suffixMap = buildLanguageSuffixMap(rawSuffixMap);
  return normalizeSuffix(suffixMap[targetLanguage]) || normalizeSuffix(defaults.suffix) || normalizeLanguage(targetLanguage);
}

function resolveTranslatedSuffixAliases(rawValue, targetLanguage, targetSuffix) {
  if (!isPlainObject(rawValue)) {
    return [];
  }
  const rawAliases = rawValue[targetLanguage];
  const values = Array.isArray(rawAliases)
    ? rawAliases
    : String(rawAliases || '').split(/[\n,;]+/u);
  const normalizedTargetSuffix = normalizeSuffix(targetSuffix).toLowerCase();
  const aliases = [];
  const seen = new Set();
  for (const item of values) {
    const normalized = normalizeSuffix(item).toLowerCase();
    if (!normalized || normalized === normalizedTargetSuffix || seen.has(normalized)) {
      continue;
    }
    aliases.push(normalized);
    seen.add(normalized);
  }
  return aliases;
}

function buildProviderDetail(override) {
  const parts = [];
  if (readString(override.base_url)) {
    parts.push(`base_url=${readString(override.base_url)}`);
  }
  if (readString(override.api_key_env)) {
    parts.push(`api_key_env=${readString(override.api_key_env)}`);
  }
  if (readString(override.api_mode)) {
    parts.push(`api_mode=${readString(override.api_mode)}`);
  }
  if (readString(override.max_tokens)) {
    parts.push(`max_tokens=${readString(override.max_tokens)}`);
  }
  if (readString(override.codex_home)) {
    parts.push(`codex_home=${readString(override.codex_home)}`);
  }
  if (readString(override.auth_file)) {
    parts.push(`auth_file=${readString(override.auth_file)}`);
  }
  return parts.join(' ');
}

function buildCliArgs(command, inputPath, profile, configPath, targetLanguage, targetSuffix, translatedSuffixAliases, timeoutSec) {
  const args = [command, '--json', '-i', inputPath];

  if (configPath) {
    args.push('--config', configPath);
  }

  pushArg(args, '--language', targetLanguage);
  pushArg(args, '--suffix', targetSuffix);
  pushArg(args, '--translated-suffix-aliases', Array.isArray(translatedSuffixAliases) ? translatedSuffixAliases.join(',') : '');
  if (command === 'translate' || command === 'run') {
    pushArg(args, '--timeout-sec', timeoutSec);
  }

  if (profile && !profile.useDefaults) {
    pushArg(args, '--provider', profile.provider);
    pushArg(args, '--model', profile.model);
    pushArg(args, '--max-tokens', profile.maxTokens);
    if (command === 'translate' || command === 'run') {
      pushArg(args, '--base-url', profile.baseUrl);
      pushArg(args, '--api-key', profile.apiKey);
      pushArg(args, '--api-key-env', profile.apiKeyEnv);
      pushArg(args, '--codex-home', profile.codexHome);
      pushArg(args, '--auth-file', profile.authFile);
      pushArg(args, '--api-mode', profile.apiMode);
    }
  }

  return args;
}

function buildEstimateMessage(targetPath, payload) {
  const summary = payload.summary || {};
  const price = payload.pricing?.selected_model || null;
  const lines = [
    `目标: ${targetPath}`,
    `目标语言: ${payload.language || '-'}`,
    `输出后缀: ${payload.suffix || '-'}`,
    `模型: ${payload.provider || 'auto'} / ${payload.model || '-'}`,
    `chunk_size: ${payload.chunk_size ?? '-'}`,
    `文件总数: ${summary.file_count ?? 0}`,
    `待翻译文件: ${summary.pending_file_count ?? 0}`,
    `跳过文件: ${summary.skipped_file_count ?? 0}`,
    `分块数: ${summary.chunk_count ?? 0}`,
    `原文 tokens: ${summary.source_tokens ?? 0}`,
    `请求输入 tokens: ${summary.request_input_tokens ?? 0}`,
  ];

  if (price && price.available) {
    lines.push(`预计输入成本: ${formatCost(price.estimated_input_cost, price.currency)}`);
    lines.push(`粗估总成本: ${formatCost(price.estimated_total_cost, price.currency)}`);
  } else {
    lines.push('价格: 当前模型未内置单价');
  }

  const featured = Array.isArray(payload.pricing?.featured_models) ? payload.pricing.featured_models : [];
  if (featured.length) {
    lines.push('');
    lines.push('推荐模型价格参考:');
    featured.slice(0, 10).forEach((item, index) => {
      if (item && item.available) {
        lines.push(`${index + 1}. ${item.label} | total≈${formatCost(item.estimated_total_cost, item.currency)}`);
      } else if (item) {
        lines.push(`${index + 1}. ${item.label} | 未内置价格`);
      }
    });
  }

  lines.push('');
  lines.push('请先在 VS Code 插件设置里配置模型和 key。');
  lines.push('下一步只会显示已配置可用 key 的模型。');
  lines.push('点“继续”后再选择翻译模型。');
  return lines.join('\n');
}

function buildStartTranslateMessage(targetPath, targetLanguage, targetSuffix, profile, priceItem, payload) {
  const summary = payload?.summary || {};
  const lines = [
    `目标: ${targetPath}`,
    `目标语言: ${targetLanguage}`,
    `输出后缀: ${targetSuffix || '-'}`,
    `已选模型: ${profile.label || `${profile.provider} / ${profile.model}`}`,
    `provider/model: ${profile.provider || 'auto'} / ${profile.model || '-'}`,
    `文件总数: ${summary.file_count ?? 0}`,
    `待翻译文件: ${summary.pending_file_count ?? 0}`,
    `跳过文件: ${summary.skipped_file_count ?? 0}`,
    `chunk_size: ${payload?.chunk_size ?? '-'}`,
    `分块数: ${summary.chunk_count ?? 0}`,
    `原文 tokens: ${summary.source_tokens ?? 0}`,
    `请求输入 tokens: ${summary.request_input_tokens ?? 0}`,
  ];

  if (priceItem && priceItem.available) {
    lines.push(`预计输入成本: ${formatCost(priceItem.estimated_input_cost, priceItem.currency)}`);
    lines.push(`粗估总成本: ${formatCost(priceItem.estimated_total_cost, priceItem.currency)}`);
  } else {
    lines.push('价格: 当前模型未内置单价');
  }

  return lines.join('\n');
}

function formatCommand(candidate, args) {
  return [candidate.command, ...candidate.baseArgs, ...sanitizeArgs(args)].map(quoteArg).join(' ');
}

function getCliCandidates(settings, workspaceDir) {
  const cliPath = readString(settings.get('cliPath'));
  const pythonPath = readString(settings.get('pythonPath')) || 'python3';
  const candidates = [];

  if (cliPath) {
    candidates.push({ command: cliPath, baseArgs: [] });
  } else {
    for (const candidatePath of getLocalCliCandidates(workspaceDir)) {
      candidates.push({ command: candidatePath, baseArgs: [] });
    }
    candidates.push({ command: 'mdtomd', baseArgs: [] });
    candidates.push({ command: pythonPath, baseArgs: ['-m', 'mdtomd'] });
    candidates.push({ command: 'python', baseArgs: ['-m', 'mdtomd'] });
    if (process.platform === 'win32') {
      candidates.push({ command: 'py', baseArgs: ['-m', 'mdtomd'] });
    }
  }

  return dedupeCandidates(candidates);
}

function getLocalCliCandidates(workspaceDir) {
  const candidates = [];
  const root = path.resolve(workspaceDir);
  const possible = process.platform === 'win32'
    ? [
        path.join(root, '.venv', 'Scripts', 'mdtomd.exe'),
        path.join(root, 'venv', 'Scripts', 'mdtomd.exe'),
      ]
    : [
        path.join(root, '.venv', 'bin', 'mdtomd'),
        path.join(root, 'venv', 'bin', 'mdtomd'),
      ];

  for (const candidate of possible) {
    if (fs.existsSync(candidate)) {
      candidates.push(candidate);
    }
  }

  if (process.platform === 'win32') {
    const roamingPython = path.join(os.homedir(), 'AppData', 'Roaming', 'Python');
    if (fs.existsSync(roamingPython)) {
      for (const version of safeReadDir(roamingPython)) {
        const candidate = path.join(roamingPython, version, 'Scripts', 'mdtomd.exe');
        if (fs.existsSync(candidate)) {
          candidates.push(candidate);
        }
      }
    }
  }

  if (process.platform === 'darwin') {
    const homeDir = os.homedir();
    const libraryPython = path.join(homeDir, 'Library', 'Python');
    if (fs.existsSync(libraryPython)) {
      for (const version of safeReadDir(libraryPython)) {
        const candidate = path.join(libraryPython, version, 'bin', 'mdtomd');
        if (fs.existsSync(candidate)) {
          candidates.push(candidate);
        }
      }
    }
  } else {
    const localBin = path.join(os.homedir(), '.local', 'bin', 'mdtomd');
    if (fs.existsSync(localBin)) {
      candidates.push(localBin);
    }
  }

  return candidates;
}

function summarizeTranslation(payload) {
  const summary = payload.summary || {};
  const fileCount = summary.file_count ?? 0;
  const successful = summary.successful ?? 0;
  const skipped = summary.skipped ?? 0;
  const failed = summary.failed ?? 0;
  return { fileCount, successful, skipped, failed, completed: successful + skipped };
}

function findPriceItem(payload, provider, model) {
  const pricing = asObject(payload.pricing);
  const candidates = [];
  if (pricing.selected_model) {
    candidates.push(pricing.selected_model);
  }
  if (Array.isArray(pricing.featured_models)) {
    candidates.push(...pricing.featured_models);
  }

  for (const item of candidates) {
    if (!item) {
      continue;
    }
    if (readString(item.provider) === readString(provider) && readString(item.model) === readString(model)) {
      return item;
    }
  }
  return null;
}

function sanitizeArgs(args) {
  const sanitized = [];
  for (let index = 0; index < args.length; index += 1) {
    const token = args[index];
    if (token === '--api-key' || token === '-k' || token === '--key') {
      sanitized.push(token);
      if (index + 1 < args.length) {
        sanitized.push('***');
        index += 1;
      }
      continue;
    }
    if (token.startsWith('--api-key=')) {
      sanitized.push('--api-key=***');
      continue;
    }
    sanitized.push(token);
  }
  return sanitized;
}

function dedupeCandidates(candidates) {
  const seen = new Set();
  return candidates.filter((candidate) => {
    const key = `${candidate.command}\u0000${candidate.baseArgs.join('\u0000')}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function safeReadDir(dirPath) {
  try {
    return fs.readdirSync(dirPath);
  } catch {
    return [];
  }
}

function getConfiguredSetting(settings, key) {
  if (!settings || typeof settings.inspect !== 'function') {
    return readString(settings?.get?.(key));
  }
  const inspected = settings.inspect(key);
  if (!inspected) {
    return '';
  }
  return readString(
    inspected.workspaceFolderValue
    ?? inspected.workspaceValue
    ?? inspected.globalValue
  );
}

function isUsableProfile(profile) {
  const inlineKey = readString(profile.apiKey);
  const envName = readString(profile.apiKeyEnv);
  const envValue = envName ? readString(process.env[envName]) : '';
  const authFile = readString(profile.authFile);
  const codexHome = readString(profile.codexHome);
  return Boolean(inlineKey || envValue || authFile || codexHome);
}

function buildLanguageSuffixMap(rawValue) {
  const suffixMap = { ...DEFAULT_LANGUAGE_SUFFIXES };
  if (!isPlainObject(rawValue)) {
    return suffixMap;
  }
  for (const [language, suffix] of Object.entries(rawValue)) {
    const normalizedLanguage = readString(language);
    const normalizedSuffix = normalizeSuffix(suffix);
    if (normalizedLanguage && normalizedSuffix) {
      suffixMap[normalizedLanguage] = normalizedSuffix;
    }
  }
  return suffixMap;
}

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function pushArg(args, name, value) {
  if (readString(value)) {
    args.push(name, readString(value));
  }
}

function readString(value) {
  return value == null ? '' : String(value).trim();
}

function normalizeSuffix(value) {
  return readString(value).replace(/^_+/u, '');
}

function normalizeLanguage(value) {
  return readString(value).toLowerCase().replace(/\s+/gu, '_');
}

function formatCost(value, currency) {
  return `${Number(value || 0).toFixed(6)} ${currency || ''}`.trim();
}

function quoteArg(value) {
  if (!/[\s"]/u.test(value)) {
    return value;
  }
  return JSON.stringify(value);
}

module.exports = {
  buildCliArgs,
  buildConfigProfiles,
  buildDirectSettingsProfiles,
  buildEstimateMessage,
  buildManualProfile,
  buildSettingsProfiles,
  buildStartTranslateMessage,
  findPriceItem,
  findNearestConfigPath,
  formatCommand,
  getCliCandidates,
  isMarkdownPath,
  loadConfigFile,
  resolveCliInstallSpec,
  resolveTranslatedSuffixAliases,
  resolveTargetLanguage,
  resolveTargetSuffix,
  summarizeTranslation,
};
