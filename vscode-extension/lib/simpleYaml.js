function loadSimpleYaml(text) {
  const lines = prepareYamlLines(text);
  if (!lines.length) {
    return {};
  }

  const [value, index] = parseYamlBlock(lines, 0, lines[0].indent);
  if (index !== lines.length) {
    throw new Error('Unexpected trailing content in config.yaml');
  }
  if (!isPlainObject(value)) {
    throw new Error('Config root must be a mapping');
  }
  return value;
}

function prepareYamlLines(text) {
  const prepared = [];
  const rawLines = String(text || '').split(/\r?\n/u);
  for (let index = 0; index < rawLines.length; index += 1) {
    const lineNumber = index + 1;
    const rawLine = rawLines[index];
    const stripped = stripInlineComment(rawLine).replace(/\s+$/u, '');
    if (!stripped.trim()) {
      continue;
    }
    if (rawLine.includes('\t')) {
      throw new Error(`Tabs are not supported in config.yaml (line ${lineNumber})`);
    }

    const indent = stripped.length - stripped.replace(/^ */u, '').length;
    prepared.push({
      indent,
      content: stripped.trim(),
      lineNumber,
    });
  }
  return prepared;
}

function stripInlineComment(line) {
  let inSingle = false;
  let inDouble = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === "'" && !inDouble) {
      inSingle = !inSingle;
      continue;
    }
    if (char === '"' && !inSingle) {
      inDouble = !inDouble;
      continue;
    }
    if (char === '#' && !inSingle && !inDouble) {
      if (index === 0 || /\s/u.test(line[index - 1])) {
        return line.slice(0, index);
      }
    }
  }
  return line;
}

function parseYamlBlock(lines, index, indent) {
  if (index >= lines.length) {
    return [{}, index];
  }
  if (lines[index].content.startsWith('- ')) {
    return parseYamlSequence(lines, index, indent);
  }
  return parseYamlMapping(lines, index, indent);
}

function parseYamlMapping(lines, index, indent) {
  const result = {};
  let currentIndex = index;

  while (currentIndex < lines.length) {
    const line = lines[currentIndex];
    if (line.indent < indent) {
      break;
    }
    if (line.indent > indent) {
      throw new Error(`Invalid indentation at line ${line.lineNumber}`);
    }
    if (line.content.startsWith('- ')) {
      break;
    }

    const [key, rawValue] = splitKeyValue(line.content, line.lineNumber);
    currentIndex += 1;
    let value;
    if (rawValue === '') {
      if (currentIndex < lines.length && lines[currentIndex].indent > indent) {
        [value, currentIndex] = parseYamlBlock(lines, currentIndex, lines[currentIndex].indent);
      } else {
        value = {};
      }
    } else {
      value = parseScalar(rawValue);
    }
    result[key] = value;
  }

  return [result, currentIndex];
}

function parseYamlSequence(lines, index, indent) {
  const result = [];
  let currentIndex = index;

  while (currentIndex < lines.length) {
    const line = lines[currentIndex];
    if (line.indent < indent) {
      break;
    }
    if (line.indent > indent) {
      throw new Error(`Invalid indentation at line ${line.lineNumber}`);
    }
    if (!line.content.startsWith('- ')) {
      break;
    }

    const itemText = line.content.slice(2).trim();
    currentIndex += 1;
    if (itemText === '') {
      let nestedValue = null;
      if (currentIndex < lines.length && lines[currentIndex].indent > indent) {
        [nestedValue, currentIndex] = parseYamlBlock(lines, currentIndex, lines[currentIndex].indent);
      }
      result.push(nestedValue);
      continue;
    }

    if (itemText.includes(':') && !itemText.startsWith('http://') && !itemText.startsWith('https://')) {
      const [key, rawValue] = splitKeyValue(itemText, line.lineNumber);
      let value;
      if (rawValue === '') {
        if (currentIndex < lines.length && lines[currentIndex].indent > indent) {
          [value, currentIndex] = parseYamlBlock(lines, currentIndex, lines[currentIndex].indent);
        } else {
          value = {};
        }
      } else {
        value = parseScalar(rawValue);
      }
      result.push({ [key]: value });
      continue;
    }

    result.push(parseScalar(itemText));
  }

  return [result, currentIndex];
}

function splitKeyValue(content, lineNumber) {
  const separatorIndex = content.indexOf(':');
  if (separatorIndex === -1) {
    throw new Error(`Expected key: value at line ${lineNumber}`);
  }
  const key = content.slice(0, separatorIndex).trim();
  if (!key) {
    throw new Error(`Empty key at line ${lineNumber}`);
  }
  return [key, content.slice(separatorIndex + 1).trim()];
}

function parseScalar(value) {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '';
  }
  if (normalized.length >= 2 && normalized[0] === normalized[normalized.length - 1] && (normalized[0] === "'" || normalized[0] === '"')) {
    return normalized.slice(1, -1);
  }

  const lowered = normalized.toLowerCase();
  if (['true', 'yes', 'on'].includes(lowered)) {
    return true;
  }
  if (['false', 'no', 'off'].includes(lowered)) {
    return false;
  }
  if (['null', 'none', '~'].includes(lowered)) {
    return null;
  }

  if (shouldParseInt(normalized)) {
    return Number.parseInt(normalized, 10);
  }
  if (/^-?\d+\.\d+$/u.test(normalized)) {
    return Number.parseFloat(normalized);
  }
  return normalized;
}

function shouldParseInt(value) {
  if (!/^-?\d+$/u.test(value)) {
    return false;
  }
  if (value === '0' || value === '-0') {
    return true;
  }
  const unsigned = value.startsWith('-') ? value.slice(1) : value;
  return !unsigned.startsWith('0');
}

function isPlainObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value);
}

module.exports = {
  loadSimpleYaml,
};
