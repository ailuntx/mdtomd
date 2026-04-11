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
  resolveTranslatedSuffixAliases,
  resolveTargetSuffix,
  summarizeTranslation,
} = require('./lib/shared');

function activate(context) {
  const outputChannel = vscode.window.createOutputChannel('mdtomd');
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
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
    const targetSuffix = resolveTargetSuffix(config, settings.get('languageSuffixes'), targetLanguage);
    const translatedSuffixAliases = resolveTranslatedSuffixAliases(
      settings.get('translatedSuffixAliases'),
      targetLanguage,
      targetSuffix
    );
    const targetLabel = describeTarget(targetPath, workspaceFolder?.uri.fsPath);

    const cwd = configPath ? path.dirname(configPath) : workspaceFolder?.uri.fsPath || searchRoot;
    const estimateResult = await runCliJson({
      command: 'estimate',
      targetPath,
      profile: null,
      configPath,
      cwd,
      targetLanguage,
      targetSuffix,
      translatedSuffixAliases,
      outputChannel,
    });
    if (!ensureCliSuccess('estimate', estimateResult, outputChannel)) {
      return;
    }

    const estimate = estimateResult.payload;
    const pendingCount = estimate.summary?.pending_file_count ?? 0;
    const fileCount = estimate.summary?.file_count ?? 0;
    if (pendingCount <= 0) {
      showStatus(`$(check) mdtomd ${targetLabel} ${fileCount}/${fileCount}`, 5000);
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
    ];
    if (profiles.length === 0) {
      const action = await vscode.window.showWarningMessage(
        '还没有可用的翻译模型。请先在 VS Code 插件设置里填写 model，并配置 apiKey 或可用的 apiKeyEnv。',
        '打开设置',
        '手动输入'
      );
      if (action === '打开设置') {
        await vscode.commands.executeCommand('workbench.action.openSettings', 'mdtomd');
        return;
      }
      if (action !== '手动输入') {
        return;
      }
    }

    const profile = await pickProfile([...profiles, buildManualProfile()], estimate);
    if (!profile) {
      return;
    }

    const selectedEstimateResult = await runCliJson({
      command: 'estimate',
      targetPath,
      profile,
      configPath,
      cwd,
      targetLanguage,
      targetSuffix,
      translatedSuffixAliases,
      outputChannel,
    });
    if (!ensureCliSuccess('estimate', selectedEstimateResult, outputChannel)) {
      return;
    }
    const selectedEstimate = selectedEstimateResult.payload;
    const selectedPendingCount = selectedEstimate.summary?.pending_file_count ?? 0;
    if (selectedPendingCount <= 0) {
      showStatus(`$(check) mdtomd ${targetLabel} ${fileCount}/${fileCount}`, 5000);
      vscode.window.showInformationMessage('按当前模型和后缀配置，没有待翻译文件。');
      return;
    }

    const startConfirmation = await vscode.window.showInformationMessage(
      buildStartTranslateMessage(
        targetPath,
        targetLanguage,
        targetSuffix,
        profile,
        findPriceItem(selectedEstimate, profile.provider, profile.model),
        selectedEstimate
      ),
      { modal: true },
      '开始翻译'
    );
    if (startConfirmation !== '开始翻译') {
      return;
    }

    showStatus(`$(sync~spin) mdtomd ${targetLabel} 0/${selectedPendingCount}`);
    const translateResult = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title: `mdtomd 翻译中: ${targetLabel}`,
        cancellable: true,
      },
      async (_, cancellationToken) =>
        runCliJson({
          command: 'translate',
          targetPath,
          profile,
          configPath,
          cwd,
          targetLanguage,
          targetSuffix,
          translatedSuffixAliases,
          outputChannel,
          cancellationToken,
        })
    );

    if (!ensureCliSuccess('translate', translateResult, outputChannel)) {
      if (translateResult.payload?.error?.stage === 'cancelled') {
        showStatus(`$(circle-slash) mdtomd 已取消 ${targetLabel}`, 8000);
      }
      return;
    }

    const translate = translateResult.payload;
    const summary = summarizeTranslation(translate);
    showStatus(`$(check) mdtomd ${targetLabel} ${summary.completed}/${summary.fileCount}`, 8000);

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
    const settings = vscode.workspace.getConfiguration('mdtomd');
    const workspaceDir = resolveWorkspaceDir();
    const cliAvailable = await hasWorkingCli(settings, workspaceDir);
    if (!cliAvailable) {
      await ensureCliReady(workspaceDir, { interactive: false });
      return;
    }
    if (!shouldAutoUpdateCli(settings)) {
      return;
    }
    if (!cliBootstrapPromise) {
      cliBootstrapPromise = syncCliPackage(settings, workspaceDir, {
        mode: 'update',
        notifySuccess: false,
        silentFailure: true,
      }).finally(() => {
        cliBootstrapPromise = null;
      });
    }
    await cliBootstrapPromise;
  }

  async function ensureCliReady(workspaceDir, { interactive }) {
    const settings = vscode.workspace.getConfiguration('mdtomd');
    const resolvedWorkspaceDir = workspaceDir || resolveWorkspaceDir();
    const cliAvailable = await hasWorkingCli(settings, resolvedWorkspaceDir);
    if (cliAvailable) {
      return true;
    }

    if (!interactive) {
      return syncCliPackage(settings, resolvedWorkspaceDir, {
        mode: 'install',
        notifySuccess: false,
        silentFailure: true,
      });
    }

    if (!cliBootstrapPromise) {
      cliBootstrapPromise = vscode.window.withProgress(
        {
          location: vscode.ProgressLocation.Notification,
          title: 'mdtomd 正在自动安装 CLI',
          cancellable: false,
        },
        async () => syncCliPackage(settings, resolvedWorkspaceDir, {
          mode: 'install',
          notifySuccess: true,
          silentFailure: false,
        })
      ).finally(() => {
        cliBootstrapPromise = null;
      });
    }
    return cliBootstrapPromise;
  }

  function shouldAutoUpdateCli(settings) {
    return !String(settings.get('cliPath') || '').trim() && Boolean(settings.get('autoUpdateCliOnStartup'));
  }

  async function syncCliPackage(settings, workspaceDir, { mode, notifySuccess, silentFailure }) {
    outputChannel.appendLine(mode === 'update' ? '开始检查并更新 mdtomd CLI。' : '未检测到 mdtomd CLI，开始自动安装。');

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
          const message = mode === 'update'
            ? 'mdtomd CLI 已更新完成。'
            : 'mdtomd CLI 已自动安装完成，现在可以直接翻译。';
          vscode.window.showInformationMessage(message);
        }
        return true;
      }
    }

    const failureMessage = mode === 'update'
      ? '自动更新 mdtomd CLI 失败，可稍后重试或手动执行: python3 -m pip install --user -U mdtomd'
      : '自动安装 mdtomd CLI 失败，请先安装 Python 3，或手动执行: python3 -m pip install --user -U mdtomd';
    return handleCliInstallFailure(failureMessage, { silentFailure });
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

  function describeTarget(targetPath, workspaceRoot) {
    if (workspaceRoot) {
      const relativePath = path.relative(workspaceRoot, targetPath);
      if (relativePath && !relativePath.startsWith('..')) {
        return relativePath;
      }
    }
    return path.basename(targetPath) || targetPath;
  }

  async function runCliJson({
    command,
    targetPath,
    profile,
    configPath,
    cwd,
    targetLanguage,
    targetSuffix,
    translatedSuffixAliases,
    outputChannel,
    cancellationToken,
  }) {
    const settings = vscode.workspace.getConfiguration('mdtomd');
    const args = buildCliArgs(
      command,
      targetPath,
      profile,
      configPath,
      targetLanguage,
      targetSuffix,
      translatedSuffixAliases,
      settings.get('timeoutSec')
    );
    const candidates = getCliCandidates(settings, cwd);
    let lastMissing = null;

    for (const candidate of candidates) {
      outputChannel.appendLine(`> ${formatCommand(candidate, args)}  (cwd=${cwd})`);
      const result = await spawnProcess(candidate.command, [...candidate.baseArgs, ...args], cwd, { cancellationToken });
      if (result.error && result.error.code === 'ENOENT') {
        lastMissing = candidate.command;
        outputChannel.appendLine(`命令不存在: ${candidate.command}`);
        continue;
      }

      if (result.cancelled) {
        return {
          ...result,
          payload: {
            command,
            ok: false,
            error: {
              stage: 'cancelled',
              message: 'user cancelled translation',
              display_message: '已取消当前翻译任务。',
            },
          },
          invocation: formatCommand(candidate, args),
        };
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
    if (payload.error?.stage === 'cancelled') {
      vscode.window.showInformationMessage(displayMessage);
      return false;
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

function spawnProcess(command, args, cwd, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd,
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    let settled = false;
    let cancellationListener = null;
    let killTimer = null;

    const cleanup = () => {
      if (cancellationListener) {
        cancellationListener.dispose();
        cancellationListener = null;
      }
      if (killTimer) {
        clearTimeout(killTimer);
        killTimer = null;
      }
    };

    const finish = (result) => {
      if (!settled) {
        settled = true;
        cleanup();
        resolve(result);
      }
    };

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    if (options.cancellationToken) {
      cancellationListener = options.cancellationToken.onCancellationRequested(() => {
        if (settled) {
          return;
        }
        try {
          child.kill('SIGTERM');
        } catch {}
        killTimer = setTimeout(() => {
          try {
            child.kill('SIGKILL');
          } catch {}
        }, 1000);
      });
    }
    child.on('error', (error) => {
      finish({ code: 1, stdout, stderr, error, cancelled: false });
    });
    child.on('close', (code) => {
      finish({
        code: code ?? 1,
        stdout,
        stderr,
        error: null,
        cancelled: Boolean(options.cancellationToken?.isCancellationRequested),
      });
    });
  });
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
