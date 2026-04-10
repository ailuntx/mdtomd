const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const vscode = require('vscode');
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
  formatCommand,
  getCliCandidates,
  isMarkdownPath,
  loadConfigFile,
  resolveTargetLanguage,
  resolveCliInstallSpec,
  summarizeTranslation,
} = require('./lib/shared');

function activate(context) {
  const outputChannel = vscode.window.createOutputChannel('mdtomd');
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  const bootstrapVersionKey = 'mdtomd.cliBootstrapVersion';
  let statusTimer = null;
  let cliBootstrapPromise = null;

  context.subscriptions.push(outputChannel, statusBar);
  context.subscriptions.push(
    vscode.commands.registerCommand('mdtomd.translateResource', (uri) =>
      translateResource(uri, { outputChannel, statusBar, clearStatusTimer: () => clearStatusTimer() })
    )
  );
  context.subscriptions.push(
    vscode.commands.registerCommand('mdtomd.translateCurrentFile', () =>
      translateResource(vscode.window.activeTextEditor?.document.uri, { outputChannel, statusBar, clearStatusTimer: () => clearStatusTimer() })
    )
  );
  void bootstrapCliOnce();

  function clearStatusTimer() {
    if (statusTimer) {
      clearTimeout(statusTimer);
      statusTimer = null;
    }
  }

  function showStatus(text, autoHideMs = 0) {
    clearStatusTimer();
    statusBar.text = text;
    statusBar.show();
    if (autoHideMs > 0) {
      statusTimer = setTimeout(() => statusBar.hide(), autoHideMs);
    }
  }

  async function translateResource(uri, state) {
    const targetUri = uri ?? vscode.window.activeTextEditor?.document.uri;
    if (!targetUri || targetUri.scheme !== 'file') {
      vscode.window.showWarningMessage('请选择一个 Markdown 文件或文件夹。');
      return;
    }

    const targetPath = targetUri.fsPath;
    const stat = await fs.promises.stat(targetPath).catch(() => null);
    if (!stat) {
      vscode.window.showErrorMessage(`目标不存在: ${targetPath}`);
      return;
    }
    if (!stat.isDirectory() && !isMarkdownPath(targetPath)) {
      vscode.window.showWarningMessage('只支持 .md / .markdown / .mdx 文件，或直接选择文件夹。');
      return;
    }

    const workspaceFolder = vscode.workspace.getWorkspaceFolder(targetUri);
    const searchRoot = stat.isDirectory() ? targetPath : path.dirname(targetPath);
    const cliReady = await ensureCliReady(searchRoot, { interactive: true });
    if (!cliReady) {
      return;
    }
    const configPath = findNearestConfigPath(searchRoot, workspaceFolder?.uri.fsPath);

    let config = {};
    if (configPath) {
      try {
        config = loadConfigFile(configPath);
      } catch (error) {
        vscode.window.showErrorMessage(`读取配置失败: ${error instanceof Error ? error.message : String(error)}`);
        return;
      }
    }

    const settings = vscode.workspace.getConfiguration('mdtomd');
    const targetLanguage = resolveTargetLanguage(config, settings.get('targetLanguage'));

    const cwd = configPath ? path.dirname(configPath) : workspaceFolder?.uri.fsPath || searchRoot;
    const estimateResult = await runCliJson({
      command: 'estimate',
      targetPath,
      profile: null,
      configPath,
      cwd,
      targetLanguage,
      outputChannel,
    });
    if (!ensureCliSuccess('estimate', estimateResult, outputChannel)) {
      return;
    }

    const estimate = estimateResult.payload;
    const pendingCount = estimate.summary?.pending_file_count ?? 0;
    const fileCount = estimate.summary?.file_count ?? 0;
    if (pendingCount <= 0) {
      showStatus(`$(check) mdtomd 已完成 ${fileCount}/${fileCount}`, 5000);
      vscode.window.showInformationMessage('没有待翻译文件，当前目标会被全部跳过。');
      return;
    }

    const confirmation = await vscode.window.showInformationMessage(
      buildEstimateMessage(targetPath, estimate),
      { modal: true },
      '继续'
    );
    if (confirmation !== '继续') {
      return;
    }

    const profiles = [
      ...buildConfigProfiles(config, configPath),
      ...buildDirectSettingsProfiles(settings),
      ...buildSettingsProfiles(settings.get('providers')),
      buildManualProfile(),
    ];
    const profile = await pickProfile(profiles, estimate);
    if (!profile) {
      return;
    }

    const startConfirmation = await vscode.window.showInformationMessage(
      buildStartTranslateMessage(targetPath, targetLanguage, profile, findPriceItem(estimate, profile.provider, profile.model)),
      { modal: true },
      '开始翻译'
    );
    if (startConfirmation !== '开始翻译') {
      return;
    }

    showStatus(`$(sync~spin) mdtomd 翻译中 0/${pendingCount}`);
    const translateResult = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: 'mdtomd 翻译中',
        cancellable: false,
      },
      async () =>
        runCliJson({
          command: 'translate',
          targetPath,
          profile,
          configPath,
          cwd,
          targetLanguage,
          outputChannel,
        })
    );

    const translate = translateResult.payload;
    const summary = summarizeTranslation(translate);
    showStatus(`$(check) mdtomd 已完成 ${summary.completed}/${summary.fileCount}`, 8000);

    if (!ensureCliSuccess('translate', translateResult, outputChannel)) {
      return;
    }

    if (summary.failed > 0) {
      for (const item of translate.results || []) {
        if (item.error) {
          outputChannel.appendLine(`失败: ${item.input_path} -> ${item.error}`);
        }
      }
      outputChannel.show(true);
      vscode.window.showWarningMessage(`翻译完成，但有 ${summary.failed} 个文件失败，详见 mdtomd 输出面板。`);
      return;
    }

    if (translate.mode === 'single' && translate.results?.[0]?.output_path) {
      vscode.window.showInformationMessage(`翻译完成: ${translate.results[0].output_path}`);
      return;
    }

    vscode.window.showInformationMessage(`翻译完成: ${summary.completed}/${summary.fileCount}`);
  }

  async function bootstrapCliOnce() {
    const extensionVersion = getExtensionVersion();
    if (context.globalState.get(bootstrapVersionKey) === extensionVersion) {
      return;
    }
    await context.globalState.update(bootstrapVersionKey, extensionVersion);
    await ensureCliReady(resolveWorkspaceDir(), { interactive: false });
  }

  async function ensureCliReady(workspaceDir, { interactive }) {
    const settings = vscode.workspace.getConfiguration('mdtomd');
    const resolvedWorkspaceDir = workspaceDir || resolveWorkspaceDir();
    const cliAvailable = await hasWorkingCli(settings, resolvedWorkspaceDir);
    if (cliAvailable) {
      return true;
    }

    if (!interactive) {
      return installCli(settings, resolvedWorkspaceDir, { notifySuccess: false, silentFailure: true });
    }

    if (!cliBootstrapPromise) {
      cliBootstrapPromise = vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'mdtomd 正在自动安装 CLI',
          cancellable: false,
        },
        async () => installCli(settings, resolvedWorkspaceDir, { notifySuccess: true, silentFailure: false })
      ).finally(() => {
        cliBootstrapPromise = null;
      });
    }
    return cliBootstrapPromise;
  }

  async function installCli(settings, workspaceDir, { notifySuccess, silentFailure }) {
    outputChannel.appendLine('未检测到 mdtomd CLI，开始自动安装。');

    const installSpec = resolveCliInstallSpec();
    for (const candidate of getPythonInstallCandidates(settings)) {
      const args = ['-m', 'pip', 'install', '--user', '-U', installSpec.packageName];
      outputChannel.appendLine(`> ${formatCommand({ command: candidate.command, baseArgs: [] }, args)}  (cwd=${workspaceDir})`);
      const result = await spawnProcess(candidate.command, args, workspaceDir);
      appendProcessOutput(outputChannel, result);
      if (result.error && result.error.code === 'ENOENT') {
        outputChannel.appendLine(`命令不存在: ${candidate.command}`);
        continue;
      }
      if (result.code === 0) {
        await tryLinkInstalledCli(candidate.command, workspaceDir, outputChannel);
      }
      if (result.code === 0 && await hasWorkingCli(settings, workspaceDir)) {
        if (notifySuccess) {
          vscode.window.showInformationMessage('mdtomd CLI 已自动安装完成，现在可以直接翻译。');
        }
        return true;
      }
    }

    return handleCliInstallFailure('自动安装 mdtomd CLI 失败，请先安装 Python 3，或手动执行: python3 -m pip install --user -U mdtomd', { silentFailure });
  }

  function handleCliInstallFailure(message, { silentFailure }) {
    if (silentFailure) {
      outputChannel.appendLine(message);
      return false;
    }
    outputChannel.show(true);
    vscode.window.showErrorMessage(message);
    return false;
  }

  async function hasWorkingCli(settings, workspaceDir) {
    const candidates = getCliCandidates(settings, workspaceDir);
    for (const candidate of candidates) {
      const result = await spawnProcess(candidate.command, [...candidate.baseArgs, 'providers'], workspaceDir);
      if (result.error && result.error.code === 'ENOENT') {
        continue;
      }
      if (result.code === 0) {
        return true;
      }
    }
    return false;
  }

  function appendProcessOutput(channel, result) {
    if (result.stdout.trim()) {
      channel.appendLine(result.stdout.trim());
    }
    if (result.stderr.trim()) {
      channel.appendLine(result.stderr.trim());
    }
  }

  function getPythonInstallCandidates(settings) {
    const candidates = [];
    const preferred = (settings.get('pythonPath') || 'python3').trim();
    if (preferred) {
      candidates.push({ command: preferred });
    }
    candidates.push({ command: 'python3' });
    candidates.push({ command: 'python' });
    if (process.platform === 'win32') {
      candidates.push({ command: 'py' });
    }

    const seen = new Set();
    return candidates.filter((candidate) => {
      if (seen.has(candidate.command)) {
        return false;
      }
      seen.add(candidate.command);
      return true;
    });
  }

  async function tryLinkInstalledCli(pythonCommand, workspaceDir, outputChannel) {
    if (process.platform === 'win32') {
      return;
    }

    const scriptPath = await resolveInstalledCliScript(pythonCommand, workspaceDir);
    if (!scriptPath) {
      return;
    }

    const pathDirs = new Set(
      String(process.env.PATH || '')
        .split(path.delimiter)
        .filter(Boolean)
        .map((item) => path.resolve(expandHomeDir(item)))
    );

    for (const candidateDir of getCliLinkDirectories()) {
      const resolvedDir = path.resolve(candidateDir);
      if (!pathDirs.has(resolvedDir)) {
        continue;
      }
      if (!(await ensureWritableDirectory(resolvedDir))) {
        continue;
      }

      const linkPath = path.join(resolvedDir, 'mdtomd');
      try {
        await fs.promises.rm(linkPath, { force: true });
        await fs.promises.symlink(scriptPath, linkPath);
        outputChannel.appendLine(`已创建命令链接: ${linkPath} -> ${scriptPath}`);
        return;
      } catch (error) {
        outputChannel.appendLine(`创建命令链接失败: ${linkPath} (${error instanceof Error ? error.message : String(error)})`);
      }
    }
  }

  async function resolveInstalledCliScript(pythonCommand, workspaceDir) {
    const result = await spawnProcess(pythonCommand, ['-m', 'site', '--user-base'], workspaceDir);
    if (result.error || result.code !== 0) {
      return '';
    }

    const userBase = String(result.stdout || '').trim().split(/\r?\n/u).pop()?.trim() || '';
    if (!userBase) {
      return '';
    }

    const scriptPath = process.platform === 'win32'
      ? path.join(userBase, 'Scripts', 'mdtomd.exe')
      : path.join(userBase, 'bin', 'mdtomd');
    try {
      await fs.promises.access(scriptPath, fs.constants.X_OK);
      return scriptPath;
    } catch {
      return '';
    }
  }

  function getCliLinkDirectories() {
    return [
      '/opt/homebrew/bin',
      '/usr/local/bin',
      path.join(os.homedir(), '.local', 'bin'),
      path.join(os.homedir(), 'bin'),
    ];
  }

  function expandHomeDir(value) {
    if (!value.startsWith('~')) {
      return value;
    }
    if (value === '~') {
      return os.homedir();
    }
    if (value.startsWith('~/')) {
      return path.join(os.homedir(), value.slice(2));
    }
    return value;
  }

  async function ensureWritableDirectory(dirPath) {
    if (dirPath.startsWith(os.homedir())) {
      await fs.promises.mkdir(dirPath, { recursive: true });
    }
    try {
      await fs.promises.access(dirPath, fs.constants.W_OK);
      return true;
    } catch {
      return false;
    }
  }

  function resolveWorkspaceDir() {
    return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || __dirname;
  }

  function getExtensionVersion() {
    const extension = vscode.extensions.getExtension('ailuntz.mdtomd-vscode');
    return extension?.packageJSON?.version || 'dev';
  }

  async function pickProfile(profiles, estimatePayload) {
    const items = profiles.map((profile) => ({
      label: profile.label,
      description: buildProfileDescription(profile, estimatePayload),
      detail: buildProfileDetail(profile),
      profile,
    }));

    const selected = await vscode.window.showQuickPick(items, {
      placeHolder: '选择要调用的 mdtomd 配置',
      matchOnDescription: true,
      matchOnDetail: true,
    });
    if (!selected) {
      return null;
    }
    if (selected.profile.isManual) {
      return promptManualProfile();
    }
    return selected.profile;
  }

  async function promptManualProfile() {
    const provider = await vscode.window.showInputBox({
      prompt: 'provider，例如 deepseek/openai/openrouter',
      placeHolder: 'deepseek',
      ignoreFocusOut: true,
    });
    if (provider === undefined || !provider.trim()) {
      return null;
    }

    const model = await vscode.window.showInputBox({
      prompt: 'model',
      placeHolder: 'deepseek-chat',
      ignoreFocusOut: true,
    });
    if (model === undefined || !model.trim()) {
      return null;
    }

    const baseUrl = await vscode.window.showInputBox({
      prompt: 'base_url，可留空',
      ignoreFocusOut: true,
    });
    if (baseUrl === undefined) {
      return null;
    }

    const apiKey = await vscode.window.showInputBox({
      prompt: 'api_key，可留空',
      password: true,
      ignoreFocusOut: true,
    });
    if (apiKey === undefined) {
      return null;
    }

    return {
      id: 'manual:filled',
      label: `临时配置 / ${provider.trim()} / ${model.trim()}`,
      description: `${provider.trim()} / ${model.trim()}`,
      detail: baseUrl.trim(),
      useDefaults: false,
      provider: provider.trim(),
      model: model.trim(),
      baseUrl: baseUrl.trim(),
      apiKey: apiKey.trim(),
      source: 'manual',
    };
  }

  function buildProfileDescription(profile, estimatePayload) {
    if (profile.isManual) {
      return profile.description;
    }
    const priceItem = findPriceItem(estimatePayload, profile.provider, profile.model);
    if (priceItem && priceItem.available) {
      return `${profile.provider} / ${profile.model} | total≈${Number(priceItem.estimated_total_cost || 0).toFixed(6)} ${priceItem.currency}`;
    }
    return profile.description || `${profile.provider || 'auto'} / ${profile.model || '-'}`;
  }

  function buildProfileDetail(profile) {
    const sourceMap = {
      'config-default': '来源: config 默认',
      'config-provider': '来源: config.providers',
      settings: '来源: VS Code 设置',
      'settings-direct': '来源: VS Code 设置',
      manual: '来源: 手动输入',
    };
    const base = sourceMap[profile.source] || '';
    return [base, profile.detail].filter(Boolean).join(' | ');
  }

  async function runCliJson({ command, targetPath, profile, configPath, cwd, targetLanguage, outputChannel }) {
    const settings = vscode.workspace.getConfiguration('mdtomd');
    const args = buildCliArgs(command, targetPath, profile, configPath, targetLanguage);
    const candidates = getCliCandidates(settings, cwd);
    let lastMissing = null;

    for (const candidate of candidates) {
      outputChannel.appendLine(`> ${formatCommand(candidate, args)}  (cwd=${cwd})`);
      const result = await spawnProcess(candidate.command, [...candidate.baseArgs, ...args], cwd);
      if (result.error && result.error.code === 'ENOENT') {
        lastMissing = candidate.command;
        outputChannel.appendLine(`命令不存在: ${candidate.command}`);
        continue;
      }

      if (result.stderr.trim()) {
        outputChannel.appendLine(result.stderr.trim());
      }

      const payload = parseCliJson(result.stdout, command, result.stderr);
      if (settings.get('showOutputChannelOnSuccess')) {
        outputChannel.show(true);
      }
      return {
        ...result,
        payload,
        invocation: formatCommand(candidate, args),
      };
    }

    return {
      code: 1,
      stdout: '',
      stderr: '',
      payload: {
        command,
        ok: false,
        error: {
          stage: 'spawn',
          message: `未找到可用的 mdtomd 命令，最后一次尝试: ${lastMissing || 'mdtomd'}`,
          display_message: '未找到 mdtomd CLI，请先安装，或在设置里配置 mdtomd.cliPath。',
        },
      },
      invocation: '',
    };
  }

  function ensureCliSuccess(command, result, outputChannel) {
    const payload = result.payload || {};
    if (!payload.error) {
      return true;
    }

    const displayMessage =
      payload.error?.display_message || payload.error?.message || `${command} 执行失败，请查看 mdtomd 输出面板。`;
    if (result.invocation) {
      outputChannel.appendLine(`[${command}] ${result.invocation}`);
    }
    if (result.stdout.trim()) {
      outputChannel.appendLine(result.stdout.trim());
    }
    if (result.stderr.trim()) {
      outputChannel.appendLine(result.stderr.trim());
    }
    outputChannel.show(true);
    vscode.window.showErrorMessage(displayMessage);
    return false;
  }
}

function parseCliJson(stdout, command, stderr) {
  const text = String(stdout || '').trim();
  if (!text) {
    return {
      command,
      ok: false,
      error: {
        stage: 'parse',
        message: 'CLI 未输出 JSON',
        display_message: 'mdtomd CLI 没有返回 JSON，详情见输出面板。',
      },
    };
  }

  try {
    return JSON.parse(text);
  } catch (error) {
    return {
      command,
      ok: false,
      error: {
        stage: 'parse',
        message: error instanceof Error ? error.message : String(error),
        display_message: 'mdtomd CLI 返回的内容不是合法 JSON，详情见输出面板。',
      },
      raw_stdout: text,
      raw_stderr: String(stderr || ''),
    };
  }
}

function spawnProcess(command, args, cwd) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd,
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    let settled = false;

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('error', (error) => {
      if (!settled) {
        settled = true;
        resolve({ code: 1, stdout, stderr, error });
      }
    });
    child.on('close', (code) => {
      if (!settled) {
        settled = true;
        resolve({ code: code ?? 1, stdout, stderr, error: null });
      }
    });
  });
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
