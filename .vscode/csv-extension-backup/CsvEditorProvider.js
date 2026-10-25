"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || function (mod) {
    if (mod && mod.__esModule) return mod;
    var result = {};
    if (mod != null) for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
    __setModuleDefault(result, mod);
    return result;
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.CsvEditorProvider = void 0;
const papaparse_1 = __importDefault(require("papaparse"));
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
// Per-document controller. Manages one webview + document.
class CsvEditorController {
    constructor(context) {
        this.context = context;
        this.isUpdatingDocument = false;
        this.isSaving = false;
        this.isDiffContext = false;
    }
    // (no static helpers here; see wrapper CsvEditorProvider)
    async resolveCustomTextEditor(document, webviewPanel, _token) {
        this.document = document;
        const config = vscode.workspace.getConfiguration('csv', this.document.uri);
        if (!config.get('enabled', true)) {
            // When disabled, immediately hand off to the default editor and close this tab
            await this.openWithDefaultEditorAndClose(webviewPanel, document.uri);
            return;
        }
        const proceed = await this.confirmLargeFileOpen(config, webviewPanel, _token);
        if (!proceed) {
            return;
        }
        this.currentWebviewPanel = webviewPanel;
        CsvEditorProvider.editors.push(this);
        webviewPanel.webview.options = {
            enableScripts: true,
            // Use file path for compatibility with older VS Code types (no Uri.joinPath)
            localResourceRoots: [vscode.Uri.file(path.join(this.context.extensionPath, 'media'))]
        };
        this.refreshDiffContext(webviewPanel);
        this.updateWebviewContent();
        if (webviewPanel.active) {
            CsvEditorProvider.currentActive = this;
        }
        webviewPanel.webview.postMessage({ type: 'focus' });
        webviewPanel.onDidChangeViewState(e => {
            if (e.webviewPanel.active) {
                const diffChanged = this.refreshDiffContext(e.webviewPanel);
                if (diffChanged) {
                    this.updateWebviewContent();
                }
                e.webviewPanel.webview.postMessage({ type: 'focus' });
                CsvEditorProvider.currentActive = this;
            }
        });
        webviewPanel.webview.onDidReceiveMessage(async (e) => {
            switch (e.type) {
                case 'editCell':
                    this.updateDocument(e.row, e.col, e.value);
                    break;
                case 'replaceCells':
                    await this.replaceCells(e.replacements);
                    break;
                case 'pasteCells':
                    await this.pasteCells(e.text, e.anchorRow, e.anchorCol, e.selection);
                    break;
                case 'requestChunk':
                    await this.requestChunk(e.start, e.requestId);
                    break;
                case 'findMatches':
                    await this.findMatches(e.requestId, e.query, e.options);
                    break;
                case 'save':
                    await this.handleSave();
                    break;
                case 'copyToClipboard':
                    await vscode.env.clipboard.writeText(e.text);
                    console.log('CSV: Copied to clipboard');
                    break;
                case 'insertColumn':
                    await this.insertColumn(e.index);
                    break;
                case 'insertColumns':
                    await this.insertColumns(e.index, e.count);
                    break;
                case 'deleteColumn':
                    await this.deleteColumn(e.index);
                    break;
                case 'deleteColumns':
                    await this.deleteColumns(e.indices);
                    break;
                case 'insertRow':
                    await this.insertRow(e.index);
                    break;
                case 'insertRows':
                    await this.insertRows(e.index, e.count);
                    break;
                case 'deleteRow':
                    await this.deleteRow(e.index);
                    break;
                case 'deleteRows':
                    await this.deleteRows(e.indices);
                    break;
                case 'reorderColumns':
                    await this.reorderColumns(e.indices, e.beforeIndex);
                    break;
                case 'reorderRows':
                    await this.reorderRows(e.indices, e.beforeIndex);
                    break;
                case 'sortColumn':
                    await this.sortColumn(e.index, e.ascending);
                    break;
                case 'openLink':
                    await this.openLinkExternally(e.url);
                    break;
            }
        });
        const changeDocumentSubscription = vscode.workspace.onDidChangeTextDocument(e => {
            if (e.document.uri.toString() === document.uri.toString() &&
                !this.isUpdatingDocument &&
                !this.isSaving) {
                setTimeout(() => this.updateWebviewContent(), 250);
            }
        });
        webviewPanel.onDidDispose(() => {
            changeDocumentSubscription.dispose();
            CsvEditorProvider.editors = CsvEditorProvider.editors.filter(ed => ed !== this);
            this.currentWebviewPanel = undefined;
        });
    }
    getMaxFileSizeLimitMb(config) {
        const raw = Number(config.get('maxFileSizeMB', CsvEditorController.DEFAULT_MAX_FILE_SIZE_MB));
        if (!Number.isFinite(raw) || raw <= 0) {
            return 0;
        }
        return raw;
    }
    shouldPromptForLargeFile(fileSizeBytes, maxFileSizeMB) {
        if (!Number.isFinite(fileSizeBytes) || fileSizeBytes < 0) {
            return false;
        }
        if (!Number.isFinite(maxFileSizeMB) || maxFileSizeMB <= 0) {
            return false;
        }
        const thresholdBytes = Math.floor(maxFileSizeMB * CsvEditorController.BYTES_PER_MB);
        return fileSizeBytes > thresholdBytes;
    }
    formatSizeMb(fileSizeBytes) {
        if (!Number.isFinite(fileSizeBytes) || fileSizeBytes <= 0) {
            return '0.0';
        }
        return (fileSizeBytes / CsvEditorController.BYTES_PER_MB).toFixed(1);
    }
    async openWithDefaultEditorAndClose(webviewPanel, uri) {
        try {
            const opts = {
                viewColumn: webviewPanel.viewColumn,
                preserveFocus: !webviewPanel.active,
                preview: webviewPanel.active ? webviewPanel.active : false
            };
            await vscode.commands.executeCommand('vscode.openWith', uri, 'default', opts);
        }
        finally {
            try {
                webviewPanel.dispose();
            }
            catch { }
        }
    }
    async confirmLargeFileOpen(config, webviewPanel, token) {
        const maxFileSizeMB = this.getMaxFileSizeLimitMb(config);
        if (maxFileSizeMB <= 0) {
            return true;
        }
        let sizeBytes = 0;
        try {
            const stat = await vscode.workspace.fs.stat(this.document.uri);
            sizeBytes = Number(stat.size);
        }
        catch (err) {
            console.warn(`CSV: unable to stat file size for ${this.document.uri.toString()}`, err);
            return true;
        }
        if (token.isCancellationRequested) {
            return false;
        }
        if (!this.shouldPromptForLargeFile(sizeBytes, maxFileSizeMB)) {
            return true;
        }
        const fileLabel = path.basename(this.document.uri.fsPath || this.document.uri.path || this.document.uri.toString());
        const selected = await vscode.window.showWarningMessage(`CSV: "${fileLabel}" is ${this.formatSizeMb(sizeBytes)} MB and exceeds the csv.maxFileSizeMB limit (${maxFileSizeMB} MB).`, {
            modal: true,
            detail: 'Opening large files in CSV view can be slow and block the editor.'
        }, CsvEditorController.LARGE_FILE_CONTINUE_THIS_TIME, CsvEditorController.LARGE_FILE_IGNORE_FOREVER);
        if (selected === CsvEditorController.LARGE_FILE_CONTINUE_THIS_TIME) {
            return true;
        }
        if (selected === CsvEditorController.LARGE_FILE_IGNORE_FOREVER) {
            await vscode.workspace
                .getConfiguration('csv')
                .update('maxFileSizeMB', 0, vscode.ConfigurationTarget.Global);
            vscode.window.showInformationMessage('CSV: Large-file prompt disabled (csv.maxFileSizeMB = 0).');
            return true;
        }
        try {
            webviewPanel.dispose();
        }
        catch { }
        return false;
    }
    refresh() {
        var _a;
        const config = vscode.workspace.getConfiguration('csv', this.document.uri);
        if (!config.get('enabled', true)) {
            (_a = this.currentWebviewPanel) === null || _a === void 0 ? void 0 : _a.dispose();
            vscode.commands.executeCommand('vscode.openWith', this.document.uri, 'default');
        }
        else {
            if (this.currentWebviewPanel) {
                this.forceReload();
            }
        }
    }
    forceReload() {
        if (!this.currentWebviewPanel)
            return;
        const panel = this.currentWebviewPanel;
        // First, blank the DOM to ensure a full script/style reinit on next set
        panel.webview.html = '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body></body></html>';
        setTimeout(() => {
            try {
                this.updateWebviewContent();
            }
            catch (err) {
                console.error('CSV: forceReload failed', err);
            }
        }, 0);
    }
    isActive() {
        var _a;
        return !!((_a = this.currentWebviewPanel) === null || _a === void 0 ? void 0 : _a.active);
    }
    refreshDiffContext(webviewPanel) {
        const next = this.isLikelyDiffContext(webviewPanel, this.document.uri);
        const changed = next !== this.isDiffContext;
        this.isDiffContext = next;
        return changed;
    }
    isLikelyDiffContext(webviewPanel, uri) {
        var _a, _b;
        if (uri.scheme === 'git') {
            return true;
        }
        const title = webviewPanel.title || '';
        if (title.includes('↔')) {
            return true;
        }
        const key = uri.toString();
        const tabGroups = (_b = (_a = vscode.window) === null || _a === void 0 ? void 0 : _a.tabGroups) === null || _b === void 0 ? void 0 : _b.all;
        if (!Array.isArray(tabGroups)) {
            return false;
        }
        for (const group of tabGroups) {
            const activeTab = group === null || group === void 0 ? void 0 : group.activeTab;
            const input = activeTab === null || activeTab === void 0 ? void 0 : activeTab.input;
            const original = input === null || input === void 0 ? void 0 : input.original;
            const modified = input === null || input === void 0 ? void 0 : input.modified;
            if (original instanceof vscode.Uri && modified instanceof vscode.Uri) {
                if (original.toString() === key || modified.toString() === key) {
                    return true;
                }
            }
        }
        return false;
    }
    static resolveEffectiveColumnColorMode(baseMode, isDiffContext, useThemeForegroundInDiff) {
        const normalizedBase = baseMode === 'theme' ? 'theme' : 'type';
        if (isDiffContext && useThemeForegroundInDiff) {
            return 'theme';
        }
        return normalizedBase;
    }
    static normalizeFontSize(value) {
        const parsed = Number(value);
        if (!Number.isFinite(parsed) || parsed <= 0) {
            return undefined;
        }
        return Math.round(parsed * 100) / 100;
    }
    static resolveEffectiveFontSize(csvFontSize, editorFontSize) {
        var _a, _b;
        return ((_b = (_a = CsvEditorController.normalizeFontSize(csvFontSize)) !== null && _a !== void 0 ? _a : CsvEditorController.normalizeFontSize(editorFontSize)) !== null && _b !== void 0 ? _b : 14);
    }
    getDocumentUri() {
        return this.document.uri;
    }
    getCurrentSeparator() {
        return this.getSeparator();
    }
    // ───────────── Document Editing Methods ─────────────
    async updateDocument(row, col, value) {
        var _a, _b;
        this.isUpdatingDocument = true;
        let structuralChange = false;
        let applied = false;
        try {
            const separator = this.getSeparator();
            const oldText = this.document.getText();
            const result = papaparse_1.default.parse(oldText, { dynamicTyping: false, delimiter: separator });
            const data = result.data;
            const hadRows = data.length;
            const hadColsAtRow = (data[row] ? data[row].length : 0);
            const previousValue = row < hadRows && col < hadColsAtRow
                ? String((_a = data[row][col]) !== null && _a !== void 0 ? _a : '')
                : undefined;
            const { data: nextData, trimmed, createdRow, createdCol } = this.mutateDataForEdit(data, row, col, value);
            structuralChange = !!(trimmed || createdRow || createdCol || row >= hadRows || col >= hadColsAtRow);
            if (!structuralChange && previousValue === value) {
                return;
            }
            let newCsvText;
            if (!structuralChange) {
                newCsvText = CsvEditorProvider.applyFieldUpdatesPreservingFormat(oldText, separator, [{ row, col, value: String(value !== null && value !== void 0 ? value : '') }]);
            }
            if (newCsvText === undefined) {
                newCsvText = papaparse_1.default.unparse(nextData, { delimiter: separator });
            }
            if (newCsvText === oldText) {
                return;
            }
            const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
            const edit = new vscode.WorkspaceEdit();
            edit.replace(this.document.uri, fullRange, newCsvText);
            await vscode.workspace.applyEdit(edit);
            applied = true;
        }
        finally {
            this.isUpdatingDocument = false;
        }
        if (!applied) {
            return;
        }
        console.log(`CSV: Updated row ${row + 1}, column ${col + 1} to "${value}"`);
        const config = vscode.workspace.getConfiguration('csv', this.document.uri);
        const clickableLinks = config.get('clickableLinks', true);
        const rendered = this.formatCellContent(value !== null && value !== void 0 ? value : '', clickableLinks);
        (_b = this.currentWebviewPanel) === null || _b === void 0 ? void 0 : _b.webview.postMessage({ type: 'updateCell', row, col, value, rendered });
        // Trigger a full re-render if structure may have changed (new row/col created)
        if (structuralChange) {
            try {
                this.updateWebviewContent();
            }
            catch (e) {
                console.error('CSV: refresh failed after structural edit', e);
            }
        }
    }
    async replaceCells(replacements) {
        var _a, _b, _c;
        if (!Array.isArray(replacements) || replacements.length === 0) {
            return;
        }
        this.isUpdatingDocument = true;
        try {
            const separator = this.getSeparator();
            const oldText = this.document.getText();
            const result = papaparse_1.default.parse(oldText, { dynamicTyping: false, delimiter: separator });
            const data = result.data;
            const updates = [];
            let changed = false;
            for (const replacement of replacements) {
                if (!replacement || typeof replacement !== 'object') {
                    continue;
                }
                const row = Number(replacement.row);
                const col = Number(replacement.col);
                if (!Number.isInteger(row) || row < 0 || !Number.isInteger(col) || col < 0) {
                    continue;
                }
                if (row >= data.length) {
                    continue;
                }
                if (col >= ((_b = (_a = data[row]) === null || _a === void 0 ? void 0 : _a.length) !== null && _b !== void 0 ? _b : 0)) {
                    continue;
                }
                const raw = replacement.value;
                const nextValue = raw === undefined || raw === null ? '' : String(raw);
                if (((_c = data[row][col]) !== null && _c !== void 0 ? _c : '') === nextValue) {
                    continue;
                }
                data[row][col] = nextValue;
                updates.push({ row, col, value: nextValue });
                changed = true;
            }
            if (!changed) {
                return;
            }
            let newCsvText = CsvEditorProvider.applyFieldUpdatesPreservingFormat(oldText, separator, updates);
            if (newCsvText === undefined) {
                newCsvText = papaparse_1.default.unparse(data, { delimiter: separator });
            }
            if (newCsvText === oldText) {
                return;
            }
            const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
            const edit = new vscode.WorkspaceEdit();
            edit.replace(this.document.uri, fullRange, newCsvText);
            await vscode.workspace.applyEdit(edit);
            this.updateWebviewContent();
        }
        finally {
            this.isUpdatingDocument = false;
        }
    }
    parseClipboardMatrix(text) {
        if (!text || text.length === 0) {
            return [];
        }
        const parsed = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: '' });
        const rowsRaw = Array.isArray(parsed.data) ? parsed.data : [];
        const matrix = rowsRaw.map(rawRow => {
            if (Array.isArray(rawRow)) {
                return rawRow.map(cell => String(cell !== null && cell !== void 0 ? cell : ''));
            }
            return [String(rawRow !== null && rawRow !== void 0 ? rawRow : '')];
        });
        while (matrix.length > 0 && matrix[matrix.length - 1].every(value => value === '')) {
            matrix.pop();
        }
        if (matrix.length === 0) {
            return [];
        }
        const width = matrix.reduce((max, row) => Math.max(max, row.length), 0);
        if (width <= 0) {
            return [];
        }
        matrix.forEach(row => {
            while (row.length < width) {
                row.push('');
            }
        });
        return matrix;
    }
    static parsePasteSelectionBounds(raw) {
        if (!raw || typeof raw !== 'object') {
            return undefined;
        }
        const minRow = Number(raw.minRow);
        const maxRow = Number(raw.maxRow);
        const minCol = Number(raw.minCol);
        const maxCol = Number(raw.maxCol);
        if (!Number.isInteger(minRow) || minRow < 0 ||
            !Number.isInteger(maxRow) || maxRow < minRow ||
            !Number.isInteger(minCol) || minCol < 0 ||
            !Number.isInteger(maxCol) || maxCol < minCol) {
            return undefined;
        }
        return {
            minRow,
            maxRow,
            minCol,
            maxCol,
            rectangular: !!raw.rectangular
        };
    }
    static computePastePlan(matrix, anchorRow, anchorCol, selection) {
        const height = matrix.length;
        const width = height > 0 ? Math.max(0, matrix[0].length) : 0;
        if (height <= 0 || width <= 0) {
            return undefined;
        }
        const canFillSelection = !!selection
            && selection.rectangular
            && (selection.maxRow > selection.minRow || selection.maxCol > selection.minCol)
            && height === 1
            && width === 1;
        if (canFillSelection) {
            return {
                startRow: selection.minRow,
                startCol: selection.minCol,
                endRow: selection.maxRow,
                endCol: selection.maxCol,
                fillSelection: true
            };
        }
        return {
            startRow: anchorRow,
            startCol: anchorCol,
            endRow: anchorRow + height - 1,
            endCol: anchorCol + width - 1,
            fillSelection: false
        };
    }
    static applyPasteMatrixToData(data, matrix, anchorRow, anchorCol, selection) {
        var _a, _b;
        const plan = CsvEditorController.computePastePlan(matrix, anchorRow, anchorCol, selection);
        if (!plan) {
            return {
                changed: false,
                structuralChange: false,
                updates: [],
                plan: {
                    startRow: anchorRow,
                    startCol: anchorCol,
                    endRow: anchorRow,
                    endCol: anchorCol,
                    fillSelection: false
                }
            };
        }
        const updates = [];
        let changed = false;
        let structuralChange = false;
        const setCellValue = (row, col, nextValue) => {
            var _a;
            const hasRow = row >= 0 && row < data.length;
            const hasCol = hasRow && col >= 0 && col < data[row].length;
            const prevValue = hasCol ? String((_a = data[row][col]) !== null && _a !== void 0 ? _a : '') : '';
            if (prevValue === nextValue) {
                return;
            }
            if (!hasRow || !hasCol) {
                structuralChange = true;
            }
            while (data.length <= row) {
                data.push([]);
            }
            while (data[row].length <= col) {
                data[row].push('');
            }
            data[row][col] = nextValue;
            updates.push({ row, col, value: nextValue });
            changed = true;
        };
        if (plan.fillSelection) {
            const value = String((_a = matrix[0][0]) !== null && _a !== void 0 ? _a : '');
            for (let row = plan.startRow; row <= plan.endRow; row++) {
                for (let col = plan.startCol; col <= plan.endCol; col++) {
                    setCellValue(row, col, value);
                }
            }
        }
        else {
            for (let r = 0; r < matrix.length; r++) {
                for (let c = 0; c < matrix[r].length; c++) {
                    setCellValue(plan.startRow + r, plan.startCol + c, String((_b = matrix[r][c]) !== null && _b !== void 0 ? _b : ''));
                }
            }
        }
        return { changed, structuralChange, updates, plan };
    }
    async pasteCells(rawText, rawAnchorRow, rawAnchorCol, rawSelection) {
        var _a;
        const text = typeof rawText === 'string' ? rawText : '';
        if (!text) {
            return;
        }
        const anchorRow = Number(rawAnchorRow);
        const anchorCol = Number(rawAnchorCol);
        if (!Number.isInteger(anchorRow) || anchorRow < 0 || !Number.isInteger(anchorCol) || anchorCol < 0) {
            return;
        }
        const matrix = this.parseClipboardMatrix(text);
        if (!matrix.length || !matrix[0].length) {
            return;
        }
        const selection = CsvEditorController.parsePasteSelectionBounds(rawSelection);
        this.isUpdatingDocument = true;
        try {
            const separator = this.getSeparator();
            const oldText = this.document.getText();
            const result = papaparse_1.default.parse(oldText, { dynamicTyping: false, delimiter: separator });
            const data = result.data;
            const pasteResult = CsvEditorController.applyPasteMatrixToData(data, matrix, anchorRow, anchorCol, selection);
            if (!pasteResult.changed) {
                return;
            }
            let newCsvText;
            if (!pasteResult.structuralChange) {
                newCsvText = CsvEditorProvider.applyFieldUpdatesPreservingFormat(oldText, separator, pasteResult.updates);
            }
            if (newCsvText === undefined) {
                newCsvText = papaparse_1.default.unparse(data, { delimiter: separator });
            }
            if (newCsvText === oldText) {
                return;
            }
            const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
            const edit = new vscode.WorkspaceEdit();
            edit.replace(this.document.uri, fullRange, newCsvText);
            await vscode.workspace.applyEdit(edit);
            this.updateWebviewContent();
            (_a = this.currentWebviewPanel) === null || _a === void 0 ? void 0 : _a.webview.postMessage({
                type: 'pasteApplied',
                startRow: pasteResult.plan.startRow,
                startCol: pasteResult.plan.startCol,
                endRow: pasteResult.plan.endRow,
                endCol: pasteResult.plan.endCol
            });
        }
        finally {
            this.isUpdatingDocument = false;
        }
    }
    renderChunkFromState(state, start) {
        if (!Number.isInteger(start) || start < 0) {
            return { html: '', nextStart: -1, done: true };
        }
        if (start < state.allRowsCount) {
            const end = Math.min(start + state.chunkRows, state.allRowsCount);
            const html = state.allRows.slice(start, end).map((row, localR) => {
                const absRow = state.startAbs + start + localR;
                const displayIdx = start + localR + 1;
                let cells = '';
                for (let cIdx = 0; cIdx < state.numColumns; cIdx++) {
                    const rawValue = row[cIdx] || '';
                    const safe = this.formatCellContent(rawValue, state.clickableLinks);
                    const titleAttr = this.getMultilineCellTitleAttr(rawValue);
                    cells += `<td tabindex="0" style="min-width:${Math.min(state.columnWidths[cIdx] || 0, 100)}ch;max-width:100ch;border:1px solid ${state.isDark ? '#555' : '#ccc'};color:${state.columnColors[cIdx]};overflow:visible;white-space: pre-wrap;overflow-wrap:anywhere;"${titleAttr} data-row="${absRow}" data-col="${cIdx}">${safe}</td>`;
                }
                const idxCell = state.addSerialIndex
                    ? `<td tabindex="0" style="min-width:${state.serialIndexWidthCh}ch;max-width:${state.serialIndexWidthCh}ch;border:1px solid ${state.isDark ? '#555' : '#ccc'};color:#888;" data-row="${absRow}" data-col="-1">${displayIdx}</td>`
                    : '';
                return `<tr>${idxCell}${cells}</tr>`;
            }).join('');
            if (end < state.allRowsCount) {
                return { html, nextStart: end, done: false };
            }
            if (state.includeTrailingEmptyRow) {
                return { html, nextStart: state.allRowsCount, done: false };
            }
            return { html, nextStart: -1, done: true };
        }
        if (start === state.allRowsCount && state.includeTrailingEmptyRow) {
            const virtualAbs = state.startAbs + state.allRowsCount;
            const displayIdx = state.allRowsCount + 1;
            const idxCell = state.addSerialIndex
                ? `<td tabindex="0" style="min-width:${state.serialIndexWidthCh}ch;max-width:${state.serialIndexWidthCh}ch;border:1px solid ${state.isDark ? '#555' : '#ccc'};color:#888;" data-row="${virtualAbs}" data-col="-1">${displayIdx}</td>`
                : '';
            const dataCells = Array.from({ length: state.numColumns }, (_, i) => `<td tabindex="0" style="min-width:${Math.min(state.columnWidths[i] || 0, 100)}ch;max-width:100ch;border:1px solid ${state.isDark ? '#555' : '#ccc'};color:${state.columnColors[i]};overflow:visible;white-space: pre-wrap;overflow-wrap:anywhere;" data-row="${virtualAbs}" data-col="${i}"></td>`).join('');
            return { html: `<tr>${idxCell}${dataCells}</tr>`, nextStart: -1, done: true };
        }
        return { html: '', nextStart: -1, done: true };
    }
    async requestChunk(rawStart, requestId) {
        if (!this.currentWebviewPanel || !this.chunkRenderState) {
            return;
        }
        const start = Number(rawStart);
        if (!Number.isInteger(start) || start < 0) {
            this.currentWebviewPanel.webview.postMessage({
                type: 'chunkData',
                requestId,
                start: -1,
                html: '',
                nextStart: -1,
                done: true
            });
            return;
        }
        const response = this.renderChunkFromState(this.chunkRenderState, start);
        this.currentWebviewPanel.webview.postMessage({
            type: 'chunkData',
            requestId,
            start,
            html: response.html,
            nextStart: response.nextStart,
            done: response.done
        });
    }
    escapeFindRegex(value) {
        return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }
    buildFindRegex(query, options) {
        if (!query)
            return undefined;
        const useRegex = !!options.regex;
        const wholeWord = !!options.wholeWord;
        const matchCase = !!options.matchCase;
        let source = useRegex ? query : this.escapeFindRegex(query);
        if (wholeWord) {
            source = `\\b(?:${source})\\b`;
        }
        const flags = matchCase ? 'g' : 'gi';
        try {
            return new RegExp(source, flags);
        }
        catch {
            return undefined;
        }
    }
    async findMatches(requestId, query, options) {
        var _a;
        if (!this.currentWebviewPanel) {
            return;
        }
        const requestQuery = typeof query === 'string' ? query : '';
        const optsRaw = (options && typeof options === 'object') ? options : {};
        const opts = {
            regex: !!optsRaw.regex,
            wholeWord: !!optsRaw.wholeWord,
            matchCase: !!optsRaw.matchCase
        };
        const postResult = (payload) => {
            var _a;
            (_a = this.currentWebviewPanel) === null || _a === void 0 ? void 0 : _a.webview.postMessage({
                type: 'findMatchesResult',
                requestId,
                matches: payload.matches,
                invalidRegex: payload.invalidRegex
            });
        };
        if (!requestQuery) {
            postResult({ matches: [], invalidRegex: false });
            return;
        }
        const regex = this.buildFindRegex(requestQuery, opts);
        if (!regex) {
            postResult({ matches: [], invalidRegex: true });
            return;
        }
        const separator = this.getSeparator();
        const parsed = papaparse_1.default.parse(this.document.getText(), { dynamicTyping: false, delimiter: separator });
        const data = this.trimTrailingEmptyRows((parsed.data || []));
        const hiddenRows = this.getHiddenRows();
        const offset = Math.min(Math.max(0, hiddenRows), data.length);
        const matches = [];
        for (let row = offset; row < data.length; row++) {
            const current = data[row] || [];
            for (let col = 0; col < current.length; col++) {
                const value = String((_a = current[col]) !== null && _a !== void 0 ? _a : '');
                regex.lastIndex = 0;
                if (regex.test(value)) {
                    matches.push({ row, col, value });
                }
            }
        }
        postResult({ matches, invalidRegex: false });
    }
    // Apply an edit to a 2D data array, enforcing virtual row/cell invariants.
    // - Empty edits on non-existent virtual row/col are ignored
    // - Non-empty edits expand rows/cols as needed
    // - When editing the last row, trailing empty rows are trimmed
    mutateDataForEdit(data, row, col, value) {
        var _a, _b;
        // Work on the same array instance (callers pass freshly parsed data)
        const hadRows = data.length;
        const hadColsAtRow = (data[row] ? data[row].length : 0);
        const wasEditingLastRow = row >= (data.length - 1);
        const rowExists = row < data.length;
        const colExists = rowExists && col < ((_b = (_a = data[row]) === null || _a === void 0 ? void 0 : _a.length) !== null && _b !== void 0 ? _b : 0);
        if (value === '') {
            if (!rowExists) {
                return { data, trimmed: false, createdRow: false, createdCol: false };
            }
            if (!colExists) {
                return { data, trimmed: false, createdRow: false, createdCol: false };
            }
            data[row][col] = '';
        }
        else {
            while (data.length <= row)
                data.push([]);
            while (data[row].length <= col)
                data[row].push('');
            data[row][col] = value;
        }
        let trimmed = false;
        if (wasEditingLastRow) {
            const isRowEmpty = (arr) => {
                var _a;
                if (!arr || arr.length === 0)
                    return true;
                for (let i = 0; i < arr.length; i++) {
                    if (((_a = arr[i]) !== null && _a !== void 0 ? _a : '') !== '')
                        return false;
                }
                return true;
            };
            while (data.length > 0 && isRowEmpty(data[data.length - 1])) {
                data.pop();
                trimmed = true;
            }
        }
        return {
            data,
            trimmed,
            createdRow: value !== '' && row >= hadRows,
            createdCol: value !== '' && col >= hadColsAtRow
        };
    }
    async handleSave() {
        this.isSaving = true;
        try {
            const success = await this.document.save();
            console.log(success ? 'CSV: Document saved' : 'CSV: Failed to save document');
        }
        catch (error) {
            console.error('CSV: Error saving document', error);
        }
        finally {
            this.isSaving = false;
        }
    }
    async insertColumn(index) {
        this.isUpdatingDocument = true;
        const separator = this.getSeparator();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        const data = result.data;
        for (const row of data) {
            if (index > row.length) {
                while (row.length < index)
                    row.push('');
            }
            row.splice(index, 0, '');
        }
        const newText = papaparse_1.default.unparse(data, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newText);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
    }
    async insertColumns(index, count) {
        if (count <= 0)
            return;
        this.isUpdatingDocument = true;
        const separator = this.getSeparator();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        const data = result.data;
        for (let k = 0; k < count; k++) {
            for (const row of data) {
                if (index > row.length) {
                    while (row.length < index)
                        row.push('');
                }
                row.splice(index, 0, '');
            }
        }
        const newText = papaparse_1.default.unparse(data, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newText);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
    }
    async deleteColumn(index) {
        this.isUpdatingDocument = true;
        const separator = this.getSeparator();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        const data = result.data;
        for (const row of data) {
            if (index < row.length) {
                row.splice(index, 1);
            }
        }
        const newText = papaparse_1.default.unparse(data, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newText);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
    }
    async deleteColumns(indices) {
        if (!indices || !indices.length)
            return;
        this.isUpdatingDocument = true;
        const separator = this.getSeparator();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        const data = result.data;
        const sorted = [...indices].sort((a, b) => b - a);
        for (const idx of sorted) {
            for (const row of data) {
                if (idx < row.length) {
                    row.splice(idx, 1);
                }
            }
        }
        const newText = papaparse_1.default.unparse(data, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newText);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
    }
    async sortColumn(index, ascending) {
        this.isUpdatingDocument = true;
        const config = vscode.workspace.getConfiguration('csv', this.document.uri);
        const separator = this.getSeparator();
        const hidden = this.getHiddenRows();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        // Exclude virtual/trailing empty rows from sort input
        const rows = this.trimTrailingEmptyRows(result.data);
        const treatHeader = this.getEffectiveHeader(rows, this.getHiddenRows());
        const offset = Math.min(Math.max(0, hidden), rows.length);
        let header = [];
        let body = [];
        if (treatHeader && offset < rows.length) {
            header = rows[offset];
            body = rows.slice(offset + 1);
        }
        else {
            body = rows.slice(offset);
        }
        const cmp = (a, b) => {
            const sa = (a !== null && a !== void 0 ? a : '').trim();
            const sb = (b !== null && b !== void 0 ? b : '').trim();
            const aEmpty = sa === '';
            const bEmpty = sb === '';
            if (aEmpty && bEmpty)
                return 0;
            if (aEmpty)
                return 1; // empty sorts last
            if (bEmpty)
                return -1;
            // Dates take precedence over numeric compare (avoid parseFloat on ISO)
            const aIsDate = this.isDate(sa);
            const bIsDate = this.isDate(sb);
            if (aIsDate && bIsDate) {
                const da = Date.parse(sa);
                const db = Date.parse(sb);
                if (!isNaN(da) && !isNaN(db))
                    return da - db;
            }
            const na = parseFloat(sa), nb = parseFloat(sb);
            if (!isNaN(na) && !isNaN(nb))
                return na - nb;
            return sa.localeCompare(sb, undefined, { sensitivity: 'base' });
        };
        body.sort((r1, r2) => {
            var _a, _b;
            const diff = cmp((_a = r1[index]) !== null && _a !== void 0 ? _a : '', (_b = r2[index]) !== null && _b !== void 0 ? _b : '');
            return ascending ? diff : -diff;
        });
        const prefix = rows.slice(0, offset);
        const combined = treatHeader ? [...prefix, header, ...body] : [...prefix, ...body];
        // Sanitize before unparse: ensure undefined/null/NaN become empty strings
        const sanitized = combined.map(r => r.map((v) => {
            if (v === undefined || v === null)
                return '';
            const t = typeof v;
            if (t === 'number') {
                return Number.isNaN(v) ? '' : String(v);
            }
            const s = String(v);
            return s.toLowerCase() === 'nan' ? '' : s;
        }));
        const newCsv = papaparse_1.default.unparse(sanitized, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newCsv);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
        console.log(`CSV: Sorted column ${index + 1} (${ascending ? 'A-Z' : 'Z-A'})`);
    }
    async insertRow(index) {
        this.isUpdatingDocument = true;
        const separator = this.getSeparator();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        const data = result.data;
        const numColumns = data.reduce((max, r) => Math.max(max, r.length), 0);
        const newRow = Array(numColumns).fill('');
        if (index > data.length) {
            while (data.length < index)
                data.push(Array(numColumns).fill(''));
        }
        data.splice(index, 0, newRow);
        const newText = papaparse_1.default.unparse(data, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newText);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
    }
    async insertRows(index, count) {
        if (count <= 0)
            return;
        this.isUpdatingDocument = true;
        const separator = this.getSeparator();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        const data = result.data;
        const numColumns = data.reduce((max, r) => Math.max(max, r.length), 0);
        for (let k = 0; k < count; k++) {
            const newRow = Array(numColumns).fill('');
            if (index > data.length) {
                while (data.length < index)
                    data.push(Array(numColumns).fill(''));
            }
            data.splice(index, 0, newRow);
        }
        const newText = papaparse_1.default.unparse(data, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newText);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
    }
    async deleteRow(index) {
        this.isUpdatingDocument = true;
        const separator = this.getSeparator();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        const data = result.data;
        if (index < data.length) {
            data.splice(index, 1);
        }
        const newText = papaparse_1.default.unparse(data, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newText);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
    }
    async deleteRows(indices) {
        if (!indices || !indices.length)
            return;
        this.isUpdatingDocument = true;
        const separator = this.getSeparator();
        const text = this.document.getText();
        const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
        const data = result.data;
        const sorted = [...indices].sort((a, b) => b - a);
        for (const idx of sorted) {
            if (idx < data.length) {
                data.splice(idx, 1);
            }
        }
        const newText = papaparse_1.default.unparse(data, { delimiter: separator });
        const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
        const edit = new vscode.WorkspaceEdit();
        edit.replace(this.document.uri, fullRange, newText);
        await vscode.workspace.applyEdit(edit);
        this.isUpdatingDocument = false;
        this.updateWebviewContent();
    }
    normalizeIndices(indices, maxExclusive) {
        if (!Array.isArray(indices) || maxExclusive <= 0)
            return [];
        const seen = new Set();
        const out = [];
        for (const raw of indices) {
            const num = Number(raw);
            if (!Number.isFinite(num))
                continue;
            const idx = Math.trunc(num);
            if (idx < 0 || idx >= maxExclusive || seen.has(idx))
                continue;
            seen.add(idx);
            out.push(idx);
        }
        out.sort((a, b) => a - b);
        return out;
    }
    reorderByIndices(items, indices, beforeIndex) {
        const selected = this.normalizeIndices(indices, items.length);
        if (!selected.length) {
            return { reordered: [...items], changed: false };
        }
        const before = Number(beforeIndex);
        const safeBefore = Number.isFinite(before) ? Math.trunc(before) : items.length;
        const clampedBefore = Math.min(Math.max(safeBefore, 0), items.length);
        const selectedSet = new Set(selected);
        const moving = selected.map(i => items[i]);
        const remaining = items.filter((_, i) => !selectedSet.has(i));
        const removedBefore = selected.filter(i => i < clampedBefore).length;
        const insertAt = Math.min(Math.max(clampedBefore - removedBefore, 0), remaining.length);
        const reordered = [...remaining.slice(0, insertAt), ...moving, ...remaining.slice(insertAt)];
        let changed = false;
        for (let i = 0; i < items.length; i++) {
            if (reordered[i] !== items[i]) {
                changed = true;
                break;
            }
        }
        return { reordered, changed };
    }
    async reorderColumns(indices, beforeIndex) {
        this.isUpdatingDocument = true;
        try {
            const separator = this.getSeparator();
            const text = this.document.getText();
            const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
            const data = result.data;
            const numColumns = data.reduce((max, row) => Math.max(max, row.length), 0);
            if (numColumns <= 0)
                return;
            const sourceOrder = Array.from({ length: numColumns }, (_, i) => i);
            const { reordered: columnOrder, changed } = this.reorderByIndices(sourceOrder, indices, beforeIndex);
            if (!changed)
                return;
            const reorderedData = data.map(row => {
                const normalized = Array.from({ length: numColumns }, (_, i) => { var _a; return (_a = row[i]) !== null && _a !== void 0 ? _a : ''; });
                const next = columnOrder.map(colIdx => { var _a; return (_a = normalized[colIdx]) !== null && _a !== void 0 ? _a : ''; });
                while (next.length > 0 && next[next.length - 1] === '') {
                    next.pop();
                }
                return next;
            });
            const newText = papaparse_1.default.unparse(reorderedData, { delimiter: separator });
            const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
            const edit = new vscode.WorkspaceEdit();
            edit.replace(this.document.uri, fullRange, newText);
            await vscode.workspace.applyEdit(edit);
            this.updateWebviewContent();
        }
        finally {
            this.isUpdatingDocument = false;
        }
    }
    async reorderRows(indices, beforeIndex) {
        this.isUpdatingDocument = true;
        try {
            const separator = this.getSeparator();
            const text = this.document.getText();
            const result = papaparse_1.default.parse(text, { dynamicTyping: false, delimiter: separator });
            const data = result.data;
            if (!data.length)
                return;
            const { reordered, changed } = this.reorderByIndices(data, indices, beforeIndex);
            if (!changed)
                return;
            const newText = papaparse_1.default.unparse(reordered, { delimiter: separator });
            const fullRange = new vscode.Range(0, 0, this.document.lineCount, this.document.lineCount ? this.document.lineAt(this.document.lineCount - 1).text.length : 0);
            const edit = new vscode.WorkspaceEdit();
            edit.replace(this.document.uri, fullRange, newText);
            await vscode.workspace.applyEdit(edit);
            this.updateWebviewContent();
        }
        finally {
            this.isUpdatingDocument = false;
        }
    }
    // ───────────── Webview Rendering ─────────────
    updateWebviewContent() {
        if (!this.currentWebviewPanel)
            return;
        const webview = this.currentWebviewPanel.webview;
        const config = vscode.workspace.getConfiguration('csv', this.document.uri);
        const addSerialIndex = CsvEditorProvider.getSerialIndexForUri(this.context, this.document.uri);
        const separator = this.getSeparator();
        const hiddenRows = this.getHiddenRows();
        let parsed;
        try {
            parsed = papaparse_1.default.parse(this.document.getText(), { dynamicTyping: false, delimiter: separator });
            console.log(`CSV: Parsed CSV data with ${parsed.data.length} rows`);
        }
        catch (error) {
            console.error('CSV: Error parsing CSV content', error);
            parsed = { data: [] };
        }
        const fontFamily = config.get('fontFamily') ||
            vscode.workspace.getConfiguration('editor').get('fontFamily', 'Menlo');
        const fontSize = CsvEditorController.resolveEffectiveFontSize(config.get('fontSize', 0), vscode.workspace.getConfiguration('editor').get('fontSize', 14));
        const cellPadding = config.get('cellPadding', 4);
        const data = this.trimTrailingEmptyRows((parsed.data || []));
        const treatHeader = this.getEffectiveHeader(data, hiddenRows);
        const clickableLinks = config.get('clickableLinks', true);
        const configuredColumnColorMode = config.get('columnColorMode', 'type');
        const diffUseThemeForeground = config.get('diffUseThemeForeground', true);
        const columnColorMode = CsvEditorController.resolveEffectiveColumnColorMode(configuredColumnColorMode, this.isDiffContext, diffUseThemeForeground);
        const columnColorPalette = config.get('columnColorPalette', 'default');
        const showTrailingEmptyRow = config.get('showTrailingEmptyRow', true);
        const mouseWheelZoomEnabled = config.get('mouseWheelZoom', true);
        const mouseWheelZoomInvert = config.get('mouseWheelZoomInvert', false);
        const { tableHtml, chunksJson, colorCss, nextChunkStart, hasRemoteChunks, chunkState } = this.generateTableAndChunks(data, treatHeader, addSerialIndex, hiddenRows, clickableLinks, columnColorMode, columnColorPalette, showTrailingEmptyRow, 
        /* maxSerializedChunks */ 0);
        this.chunkRenderState = chunkState;
        const nonce = this.getNonce();
        this.currentWebviewPanel.webview.html = this.wrapHtml({
            webview,
            nonce,
            fontFamily,
            fontSize,
            cellPadding,
            separator,
            tableHtml,
            chunksJson,
            extraColumnColorCss: colorCss,
            nextChunkStart,
            hasRemoteChunks,
            mouseWheelZoomEnabled,
            mouseWheelZoomInvert
        });
    }
    generateTableAndChunks(data, treatHeader, addSerialIndex, hiddenRows, clickableLinks, columnColorMode, columnColorPalette, showTrailingEmptyRow, maxSerializedChunks = Number.MAX_SAFE_INTEGER) {
        let headerFlag = treatHeader;
        const totalRows = data.length;
        const offset = Math.min(Math.max(0, hiddenRows), totalRows);
        const isDark = vscode.window.activeColorTheme.kind === vscode.ColorThemeKind.Dark;
        let headerRow = [];
        let bodyData = [];
        if (totalRows === 0 || offset >= totalRows) {
            headerFlag = false;
            bodyData = [];
        }
        else if (headerFlag) {
            headerRow = data[offset];
            bodyData = data.slice(offset + 1);
        }
        else {
            bodyData = data.slice(offset);
        }
        const visibleForWidth = headerFlag ? [headerRow, ...bodyData] : bodyData;
        let numColumns = visibleForWidth.reduce((max, row) => Math.max(max, row.length), 0);
        if (numColumns === 0)
            numColumns = 1; // ensure at least 1 column for the virtual row
        const columnData = Array.from({ length: numColumns }, (_, i) => bodyData.map(row => row[i] || ''));
        const columnTypes = columnData.map(col => this.estimateColumnDataType(col));
        const useThemeForeground = columnColorMode === 'theme';
        const palette = columnColorPalette === 'cool'
            ? 'cool'
            : (columnColorPalette === 'warm' ? 'warm' : 'default');
        const columnColors = useThemeForeground
            ? Array.from({ length: numColumns }, () => 'var(--vscode-editor-foreground)')
            : columnTypes.map((type, i) => this.getColumnColor(type, isDark, i, palette));
        const columnWidths = this.computeColumnWidths(visibleForWidth);
        const BASE_CHUNK_ROWS = 1000;
        const MAX_CELLS_PER_CHUNK = 20000;
        const MIN_CHUNK_ROWS = 10;
        const allRows = headerFlag ? data.slice(offset + 1) : data.slice(offset);
        const allRowsCount = allRows.length; // preserve total before any truncation
        const chunkRows = Math.max(MIN_CHUNK_ROWS, Math.min(BASE_CHUNK_ROWS, Math.floor(MAX_CELLS_PER_CHUNK / Math.max(1, numColumns))));
        // Always keep one editable row for fully empty views; otherwise allow disabling the
        // trailing virtual row via settings.
        const includeTrailingEmptyRow = showTrailingEmptyRow || allRowsCount === 0;
        const serialIndexMaxDisplay = includeTrailingEmptyRow ? allRowsCount + 1 : allRowsCount;
        const serialIndexWidthCh = Math.max(4, String(Math.max(1, serialIndexMaxDisplay)).length + 1);
        const chunks = [];
        const chunked = allRowsCount > chunkRows;
        let nextChunkStart = -1;
        const safeMaxSerializedChunks = Number.isFinite(maxSerializedChunks)
            ? Math.max(0, Math.trunc(maxSerializedChunks))
            : 0;
        let serializedChunkCount = 0;
        if (chunked) {
            for (let i = chunkRows; i < allRowsCount; i += chunkRows) {
                if (serializedChunkCount >= safeMaxSerializedChunks) {
                    nextChunkStart = i;
                    break;
                }
                const htmlChunk = allRows.slice(i, i + chunkRows).map((row, localR) => {
                    const startAbs = headerFlag ? offset + 1 : offset;
                    const absRow = startAbs + i + localR;
                    const displayIdx = i + localR + 1; // numbering relative to first visible data row
                    let cells = '';
                    for (let cIdx = 0; cIdx < numColumns; cIdx++) {
                        const rawValue = row[cIdx] || '';
                        const safe = this.formatCellContent(rawValue, clickableLinks);
                        const titleAttr = this.getMultilineCellTitleAttr(rawValue);
                        cells += `<td tabindex="0" style="min-width:${Math.min(columnWidths[cIdx] || 0, 100)}ch;max-width:100ch;border:1px solid ${isDark ? '#555' : '#ccc'};color:${columnColors[cIdx]};overflow:visible;white-space: pre-wrap;overflow-wrap:anywhere;"${titleAttr} data-row="${absRow}" data-col="${cIdx}">${safe}</td>`;
                    }
                    return `<tr>${addSerialIndex ? `<td tabindex="0" style="min-width:${serialIndexWidthCh}ch;max-width:${serialIndexWidthCh}ch;border:1px solid ${isDark ? '#555' : '#ccc'};color:#888;" data-row="${absRow}" data-col="-1">${displayIdx}</td>` : ''}${cells}</tr>`;
                }).join('');
                chunks.push(htmlChunk);
                serializedChunkCount++;
            }
        }
        const colorCss = useThemeForeground
            ? ''
            : columnColors.map((hex, i) => `td[data-col="${i}"], th[data-col="${i}"] { color: ${hex}; }`).join('');
        let tableHtml = `<table>`;
        if (headerFlag) {
            tableHtml += `<thead><tr>${addSerialIndex
                ? `<th tabindex="0" style="min-width: ${serialIndexWidthCh}ch; max-width: ${serialIndexWidthCh}ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; background-color: ${isDark ? '#1e1e1e' : '#ffffff'}; color: #888;"></th>`
                : ''}`;
            for (let i = 0; i < numColumns; i++) {
                const safe = this.formatCellContent(headerRow[i] || '', clickableLinks);
                tableHtml += `<th tabindex="0" style="min-width: ${Math.min(columnWidths[i] || 0, 100)}ch; max-width: 100ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; background-color: ${isDark ? '#1e1e1e' : '#ffffff'}; color: ${columnColors[i]}; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;" data-row="${offset}" data-col="${i}">${safe}</th>`;
            }
            tableHtml += `</tr></thead><tbody>`;
            const initialBodyRows = chunked ? allRows.slice(0, chunkRows) : allRows;
            initialBodyRows.forEach((row, r) => {
                tableHtml += `<tr>${addSerialIndex
                    ? `<td tabindex="0" style="min-width: ${serialIndexWidthCh}ch; max-width: ${serialIndexWidthCh}ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: #888;" data-row="${offset + 1 + r}" data-col="-1">${r + 1}</td>`
                    : ''}`;
                for (let i = 0; i < numColumns; i++) {
                    const rawValue = row[i] || '';
                    const safe = this.formatCellContent(rawValue, clickableLinks);
                    const titleAttr = this.getMultilineCellTitleAttr(rawValue);
                    tableHtml += `<td tabindex="0" style="min-width: ${Math.min(columnWidths[i] || 0, 100)}ch; max-width: 100ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: ${columnColors[i]}; overflow: visible; white-space: pre-wrap; overflow-wrap: anywhere;"${titleAttr} data-row="${offset + 1 + r}" data-col="${i}">${safe}</td>`;
                }
                tableHtml += `</tr>`;
            });
            if (!chunked && includeTrailingEmptyRow) {
                const virtualAbs = offset + 1 + initialBodyRows.length;
                const idxCell = addSerialIndex ? `<td tabindex="0" style="min-width: ${serialIndexWidthCh}ch; max-width: ${serialIndexWidthCh}ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: #888;" data-row="${virtualAbs}" data-col="-1">${initialBodyRows.length + 1}</td>` : '';
                const dataCells = Array.from({ length: numColumns }, (_, i) => `<td tabindex="0" style="min-width: ${Math.min(columnWidths[i] || 0, 100)}ch; max-width: 100ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: ${columnColors[i]}; overflow: visible; white-space: pre-wrap; overflow-wrap: anywhere;" data-row="${virtualAbs}" data-col="${i}"></td>`).join('');
                tableHtml += `<tr>${idxCell}${dataCells}</tr>`;
            }
            tableHtml += `</tbody>`;
        }
        else {
            tableHtml += `<tbody>`;
            const nonHeaderRows = chunked ? allRows.slice(0, chunkRows) : allRows;
            nonHeaderRows.forEach((row, r) => {
                tableHtml += `<tr>${addSerialIndex
                    ? `<td tabindex="0" style="min-width: ${serialIndexWidthCh}ch; max-width: ${serialIndexWidthCh}ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: #888;" data-row="${offset + r}" data-col="-1">${r + 1}</td>`
                    : ''}`;
                for (let i = 0; i < numColumns; i++) {
                    const rawValue = row[i] || '';
                    const safe = this.formatCellContent(rawValue, clickableLinks);
                    const titleAttr = this.getMultilineCellTitleAttr(rawValue);
                    tableHtml += `<td tabindex="0" style="min-width: ${Math.min(columnWidths[i] || 0, 100)}ch; max-width: 100ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: ${columnColors[i]}; overflow: visible; white-space: pre-wrap; overflow-wrap: anywhere;"${titleAttr} data-row="${offset + r}" data-col="${i}">${safe}</td>`;
                }
                tableHtml += `</tr>`;
            });
            if (!chunked && includeTrailingEmptyRow) {
                const virtualAbs = offset + nonHeaderRows.length;
                const displayIdx = nonHeaderRows.length + 1;
                const idxCell = addSerialIndex ? `<td tabindex="0" style="min-width: ${serialIndexWidthCh}ch; max-width: ${serialIndexWidthCh}ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: #888;" data-row="${virtualAbs}" data-col="-1">${displayIdx}</td>` : '';
                const dataCells = Array.from({ length: numColumns }, (_, i) => `<td tabindex="0" style="min-width: ${Math.min(columnWidths[i] || 0, 100)}ch; max-width: 100ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: ${columnColors[i]}; overflow: visible; white-space: pre-wrap; overflow-wrap: anywhere;" data-row="${virtualAbs}" data-col="${i}"></td>`).join('');
                tableHtml += `<tr>${idxCell}${dataCells}</tr>`;
            }
            tableHtml += `</tbody>`;
        }
        tableHtml += `</table>`;
        // If chunked, append a final chunk with the virtual row so it appears at the end.
        if (chunked && includeTrailingEmptyRow) {
            if (nextChunkStart === -1 && serializedChunkCount < safeMaxSerializedChunks) {
                const startAbs = headerFlag ? offset + 1 : offset;
                const virtualAbs = startAbs + allRowsCount;
                const displayIdx = allRowsCount + 1;
                const idxCell = addSerialIndex ? `<td tabindex="0" style="min-width: ${serialIndexWidthCh}ch; max-width: ${serialIndexWidthCh}ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: #888;" data-row="${virtualAbs}" data-col="-1">${displayIdx}</td>` : '';
                const dataCells = Array.from({ length: numColumns }, (_, i) => `<td tabindex="0" style="min-width: ${Math.min(columnWidths[i] || 0, 100)}ch; max-width: 100ch; border: 1px solid ${isDark ? '#555' : '#ccc'}; color: ${columnColors[i]}; overflow: visible; white-space: pre-wrap; overflow-wrap: anywhere;" data-row="${virtualAbs}" data-col="${i}"></td>`).join('');
                const vrow = `<tr>${idxCell}${dataCells}</tr>`;
                chunks.push(vrow);
            }
            else if (nextChunkStart === -1) {
                nextChunkStart = allRowsCount;
            }
        }
        const hasRemoteChunks = nextChunkStart >= 0;
        const chunkState = chunked
            ? {
                startAbs: headerFlag ? offset + 1 : offset,
                allRows,
                allRowsCount,
                chunkRows,
                includeTrailingEmptyRow,
                addSerialIndex,
                numColumns,
                columnWidths,
                columnColors,
                clickableLinks,
                isDark,
                serialIndexWidthCh
            }
            : undefined;
        return {
            tableHtml,
            chunksJson: JSON.stringify(chunks),
            colorCss,
            nextChunkStart,
            hasRemoteChunks,
            chunkState
        };
    }
    // Heuristic: If there is no explicit override for this file, compute default header as
    // true when the first visible row's per-column types differ from the body columns' types.
    // If they match identically across all columns, assume the first row is data (not header).
    getEffectiveHeader(data, hiddenRows) {
        // If user overrode per-file setting, honor it
        if (CsvEditorProvider.hasHeaderOverride(this.context, this.document.uri)) {
            return CsvEditorProvider.getHeaderForUri(this.context, this.document.uri);
        }
        const total = data.length;
        const offset = Math.min(Math.max(0, hiddenRows), total);
        if (total === 0 || offset >= total)
            return false; // nothing visible
        const headerRow = data[offset] || [];
        const body = data.slice(offset + 1);
        if (body.length === 0) {
            return true; // with only one row visible, lean toward header
        }
        const numColumns = body.reduce((max, r) => Math.max(max, r.length), Math.max(headerRow.length, 0));
        const bodyColData = Array.from({ length: numColumns }, (_, i) => body.map(r => r[i] || ''));
        const bodyTypes = bodyColData.map(col => this.estimateColumnDataType(col));
        const headerTypes = Array.from({ length: numColumns }, (_, i) => this.estimateColumnDataType([headerRow[i] || '']));
        const matches = headerTypes.every((t, i) => t === bodyTypes[i]);
        return !matches;
    }
    wrapHtml(args) {
        const { webview, nonce, fontFamily, fontSize, cellPadding, separator, tableHtml, chunksJson, extraColumnColorCss, nextChunkStart, hasRemoteChunks, mouseWheelZoomEnabled, mouseWheelZoomInvert } = args;
        const isDark = vscode.window.activeColorTheme.kind === vscode.ColorThemeKind.Dark;
        // Build script URI using file path for compatibility (older APIs may lack Uri.joinPath)
        const scriptUri = webview.asWebviewUri(vscode.Uri.file(path.join(this.context.extensionPath, 'media', 'main.js')));
        // Safe separator transport (assumes single character; see assumptions)
        const sepCode = (separator && separator.length > 0) ? separator.codePointAt(0) : ','.codePointAt(0);
        return `<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy"
          content="default-src 'none'; img-src ${webview.cspSource} https:; style-src 'unsafe-inline' ${webview.cspSource}; script-src 'nonce-${nonce}' ${webview.cspSource};">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CSV</title>
    <style nonce="${nonce}">
      body { font-family: ${this.escapeCss(fontFamily)}; font-size: ${fontSize}px; margin: 0; padding: 0; user-select: none; }
      .table-container { overflow: auto; height: 100vh; }
      table { border-collapse: collapse; width: max-content; }
      th, td { padding: ${cellPadding}px 8px; border: 1px solid ${isDark ? '#555' : '#ccc'}; font-size: inherit; }
      th { position: sticky; top: 0; background-color: ${isDark ? '#1e1e1e' : '#ffffff'}; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
      td { overflow: visible; white-space: pre-wrap; overflow-wrap: anywhere; }
      td.selected, th.selected { background-color: ${isDark ? '#333333' : '#cce0ff'} !important; }
      td.editing, th.editing { overflow: visible !important; white-space: pre-wrap !important; overflow-wrap: anywhere !important; max-width: none !important; }
      .highlight { background-color: ${isDark ? '#2a2a2a' : '#fefefe'} !important; }
      .active-match { background-color: ${isDark ? '#444444' : '#ffffcc'} !important; }
      .csv-link { color: ${isDark ? '#6cb6ff' : '#0066cc'}; text-decoration: underline; cursor: pointer; }
      .csv-link:hover { color: ${isDark ? '#8ecfff' : '#0044aa'}; }
      #findReplaceWidget {
        position: fixed;
        top: 12px;
        right: 20px;
        width: 592px;
        min-width: 592px;
        max-width: 592px;
        background: #171717;
        border: 1px solid #2a2a2a;
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.45);
        z-index: 1200;
        display: none;
        align-items: stretch;
        color: #d4d4d4;
        font-family: ${this.escapeCss(fontFamily)};
        font-size: inherit;
      }
      #findReplaceWidget.open { display: flex; }
      #findReplaceWidget .fr-gutter {
        width: 24px;
        min-width: 24px;
        border-radius: 6px;
        background: #2a2b2b;
        border-right: 1px solid #1f1f1f;
        margin-right: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      #findReplaceWidget .fr-content {
        flex: 1 1 auto;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      #findReplaceWidget.replace-collapsed .fr-row-replace { display: none; }
      #findReplaceWidget .fr-row {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      #findReplaceWidget .fr-row-find .fr-input-wrap {
        flex: 0 0 calc(25ch + 118px);
        width: calc(25ch + 118px);
      }
      #findReplaceWidget .fr-row-replace .fr-input-wrap {
        flex: 0 0 calc(25ch + 54px);
        width: calc(25ch + 54px);
      }
      #findReplaceWidget .fr-input-wrap {
        position: relative;
        flex: 1 1 auto;
        min-width: 0;
      }
      #findReplaceWidget .fr-input {
        width: 100%;
        height: 36px;
        box-sizing: border-box;
        border: 1px solid #2a2a2a;
        border-radius: 6px;
        background: #1c1c1c;
        color: #d4d4d4;
        padding-left: 10px;
        font-size: inherit;
        outline: none;
      }
      #findReplaceWidget .fr-input::placeholder { color: #6a6a6a; }
      #findReplaceWidget .fr-input:focus {
        border-color: #3a3a3a;
        box-shadow: 0 0 0 2px rgba(255,255,255,0.06);
      }
      #findInput { padding-right: 118px; }
      #replaceInput { padding-right: 54px; }
      #findReplaceWidget .fr-inline-toggles {
        position: absolute;
        right: 6px;
        top: 50%;
        transform: translateY(-50%);
        display: flex;
        align-items: center;
        gap: 4px;
        padding-left: 6px;
        border-left: 1px solid rgba(42,42,42,0.75);
      }
      #findReplaceWidget .fr-toggle-btn {
        min-width: 24px;
        height: 24px;
        border: 0;
        border-radius: 4px;
        background: transparent;
        color: rgba(189,189,189,0.8);
        font-size: 0.86em;
        cursor: pointer;
        padding: 0 4px;
      }
      #findReplaceWidget .fr-toggle-btn:hover { background: rgba(255,255,255,0.04); color: #e6e6e6; }
      #findReplaceWidget .fr-toggle-btn[aria-pressed="true"] {
        color: #e6e6e6;
        box-shadow: inset 0 -2px 0 #e6e6e6;
      }
      #findReplaceWidget .fr-status {
        min-width: 84px;
        text-align: right;
        color: #d0d0d0;
        font-size: inherit;
      }
      #findReplaceWidget .fr-divider {
        width: 1px;
        height: 22px;
        background: #2a2a2a;
      }
      #findReplaceWidget .fr-icon-btn,
      #findReplaceWidget .fr-action-btn,
      #findReplaceWidget .fr-caret-btn {
        width: 28px;
        height: 28px;
        border: 1px solid transparent;
        border-radius: 4px;
        background: transparent;
        color: #bdbdbd;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0;
      }
      #findReplaceWidget .fr-icon-btn:hover,
      #findReplaceWidget .fr-action-btn:hover,
      #findReplaceWidget .fr-caret-btn:hover {
        background: rgba(255,255,255,0.05);
        color: #e6e6e6;
      }
      #findReplaceWidget .fr-icon-btn[disabled],
      #findReplaceWidget .fr-action-btn[disabled] {
        color: #6a6a6a;
        cursor: default;
        pointer-events: none;
      }
      #findReplaceWidget .fr-close-btn:hover { background: rgba(255,255,255,0.08); color: #ffffff; }
      #findReplaceWidget .fr-actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      #findReplaceWidget .fr-overflow-menu {
        position: absolute;
        top: 48px;
        right: 44px;
        min-width: 200px;
        background: #202020;
        border: 1px solid #2f2f2f;
        border-radius: 6px;
        box-shadow: 0 10px 24px rgba(0,0,0,0.45);
        padding: 4px;
        display: none;
      }
      #findReplaceWidget .fr-overflow-menu.open { display: block; }
      #findReplaceWidget .fr-overflow-item {
        width: 100%;
        border: 0;
        background: transparent;
        color: #d4d4d4;
        border-radius: 4px;
        text-align: left;
        padding: 6px 8px;
        cursor: pointer;
        font-size: inherit;
      }
      #findReplaceWidget .fr-overflow-item:hover { background: rgba(255,255,255,0.05); }
      #contextMenu { position: absolute; display: none; background: ${isDark ? '#2d2d2d' : '#ffffff'}; border: 1px solid ${isDark ? '#555' : '#ccc'}; z-index: 10000; font-family: ${this.escapeCss(fontFamily)}; font-size: inherit; }
      #contextMenu div { padding: 4px 12px; cursor: pointer; }
      #contextMenu div:hover { background: ${isDark ? '#3d3d3d' : '#eeeeee'}; }

      /* Per-column computed colors */
      ${extraColumnColorCss}
    </style>
  </head>
  <body>
    <div id="csv-root" class="table-container" data-sepcode="${sepCode}" data-fontsize="${fontSize}" data-wheelzoomenabled="${mouseWheelZoomEnabled ? '1' : '0'}" data-wheelzoominvert="${mouseWheelZoomInvert ? '1' : '0'}" data-nextchunkstart="${nextChunkStart >= 0 ? nextChunkStart : ''}" data-hasmorechunks="${hasRemoteChunks ? '1' : '0'}">
      ${tableHtml}
    </div>

    <script id="__csvChunks" type="application/json" nonce="${nonce}">${chunksJson}</script>

    <div id="findReplaceWidget" class="replace-collapsed" role="group" aria-label="Find and Replace">
      <div id="replaceToggleGutter" class="fr-gutter">
        <button id="replaceToggle" class="fr-caret-btn" type="button" aria-label="Toggle Replace" aria-expanded="false">›</button>
      </div>
      <div class="fr-content">
        <div class="fr-row fr-row-find">
          <div class="fr-input-wrap">
            <input id="findInput" class="fr-input" type="text" placeholder="Find" aria-label="Find">
            <div class="fr-inline-toggles">
              <button id="findCaseToggle" class="fr-toggle-btn" type="button" aria-label="Match Case" aria-pressed="false" title="Match Case">Aa</button>
              <button id="findWordToggle" class="fr-toggle-btn" type="button" aria-label="Match Whole Word" aria-pressed="false" title="Match Whole Word">ab</button>
              <button id="findRegexToggle" class="fr-toggle-btn" type="button" aria-label="Use Regular Expression" aria-pressed="false" title="Use Regular Expression">.*</button>
            </div>
          </div>
          <div id="findStatus" class="fr-status">No results</div>
          <div class="fr-divider" aria-hidden="true"></div>
          <button id="findPrev" class="fr-icon-btn" type="button" aria-label="Previous Match" title="Previous Match" disabled>↑</button>
          <button id="findNext" class="fr-icon-btn" type="button" aria-label="Next Match" title="Next Match" disabled>↓</button>
          <button id="findMenuButton" class="fr-icon-btn" type="button" aria-label="More Find Options" title="More Find Options">☰</button>
          <button id="findClose" class="fr-icon-btn fr-close-btn" type="button" aria-label="Close Find and Replace" title="Close">✕</button>
        </div>
        <div class="fr-row fr-row-replace">
          <div class="fr-input-wrap">
            <input id="replaceInput" class="fr-input" type="text" placeholder="Replace" aria-label="Replace">
            <div class="fr-inline-toggles">
              <button id="replaceCaseToggle" class="fr-toggle-btn" type="button" aria-label="Preserve Case" aria-pressed="false" title="Preserve Case">AB</button>
            </div>
          </div>
          <div class="fr-actions">
            <button id="replaceOne" class="fr-action-btn" type="button" aria-label="Replace" title="Replace" disabled>↵</button>
            <button id="replaceAll" class="fr-action-btn" type="button" aria-label="Replace All" title="Replace All" disabled>⇅</button>
          </div>
        </div>
        <div id="findOverflowMenu" class="fr-overflow-menu" role="menu" aria-label="Find Options">
          <button id="findOverflowSelection" class="fr-overflow-item" type="button" role="menuitem">Find in selection</button>
          <button id="findOverflowDiacritics" class="fr-overflow-item" type="button" role="menuitem">Match diacritics</button>
          <button id="findOverflowPreserveCase" class="fr-overflow-item" type="button" role="menuitem">Toggle preserve case</button>
        </div>
      </div>
    </div>
    <div id="contextMenu"></div>

    <script nonce="${nonce}" src="${scriptUri}"></script>
  </body>
</html>`;
    }
    // ───────────── Utilities ─────────────
    computeColumnWidths(data) {
        const numColumns = data.reduce((max, row) => Math.max(max, row.length), 0);
        const widths = Array(numColumns).fill(0);
        for (const row of data) {
            for (let i = 0; i < numColumns; i++) {
                widths[i] = Math.max(widths[i], (row[i] || '').length);
            }
        }
        console.log(`CSV: Column widths: ${widths}`);
        return widths;
    }
    getSeparator() {
        var _a, _b;
        const stored = CsvEditorProvider.getSeparatorForUri(this.context, this.document.uri);
        if (stored && stored.length)
            return stored;
        const settings = CsvEditorProvider.getSeparatorSettings(this.document.uri);
        const configKey = CsvEditorProvider.serializeSeparatorSettings(settings);
        const version = this.document.version;
        if (this.separatorCache &&
            this.separatorCache.version === version &&
            this.separatorCache.configKey === configKey) {
            return this.separatorCache.separator;
        }
        const filePath = ((_a = this.document) === null || _a === void 0 ? void 0 : _a.uri.fsPath) || ((_b = this.document) === null || _b === void 0 ? void 0 : _b.uri.path) || '';
        const text = this.document.getText();
        const separator = CsvEditorProvider.resolveInheritedSeparator(filePath, text, settings);
        this.separatorCache = { version, configKey, separator };
        return separator;
    }
    getHiddenRows() {
        return CsvEditorProvider.getHiddenRowsForUri(this.context, this.document.uri);
    }
    escapeHtml(text) {
        return text.replace(/[&<>"']/g, m => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        })[m]);
    }
    isAllowedExternalScheme(scheme) {
        const normalized = scheme.toLowerCase();
        return normalized === 'http' || normalized === 'https' || normalized === 'ftp' || normalized === 'mailto';
    }
    isAllowedExternalUrl(rawUrl) {
        if (typeof rawUrl !== 'string')
            return false;
        const value = rawUrl.trim();
        if (!value)
            return false;
        try {
            const parsed = new URL(value);
            const scheme = parsed.protocol.replace(/:$/, '').toLowerCase();
            return this.isAllowedExternalScheme(scheme);
        }
        catch {
            return false;
        }
    }
    async openLinkExternally(rawUrl) {
        if (!this.isAllowedExternalUrl(rawUrl)) {
            return;
        }
        const value = rawUrl.trim();
        try {
            await vscode.env.openExternal(vscode.Uri.parse(value));
        }
        catch (err) {
            console.warn(`CSV: Failed to open external link: ${value}`, err);
        }
    }
    linkifyUrls(escapedText) {
        // Match URLs in already-escaped text (handles &amp; in query strings).
        // Supports http, https, ftp, mailto, and www.*.* (Google Sheets-like behavior).
        const urlPattern = /\b(?:(?:https?:\/\/|ftp:\/\/|mailto:)[^\s<>&"']+(?:&amp;[^\s<>&"']+)*|www\.[^\s<>&"']+\.[^\s<>&"']+)/gi;
        return escapedText.replace(urlPattern, (rawMatch) => {
            let matched = rawMatch;
            let trailing = '';
            const trailingMatch = matched.match(/[.,!?;:)\]]+$/);
            if (trailingMatch) {
                trailing = trailingMatch[0];
                matched = matched.slice(0, -trailing.length);
            }
            if (!matched) {
                return rawMatch;
            }
            // Decode &amp; back to & for URL parsing and opening.
            let href = matched.replace(/&amp;/g, '&');
            if (/^www\./i.test(href)) {
                href = `https://${href}`;
            }
            if (!this.isAllowedExternalUrl(href)) {
                return rawMatch;
            }
            return `<span class="csv-link" data-href="${this.escapeHtml(href)}" title="Ctrl/Cmd+click to open">${matched}</span>${trailing}`;
        });
    }
    formatCellContent(text, linkify) {
        const escaped = this.escapeHtml(text);
        return linkify ? this.linkifyUrls(escaped) : escaped;
    }
    getMultilineCellTitleAttr(text) {
        if (!text || (text.indexOf('\n') === -1 && text.indexOf('\r') === -1)) {
            return '';
        }
        return ` title="${this.escapeHtml(text)}"`;
    }
    escapeCss(text) {
        // conservative; ok for font-family lists
        return text.replace(/[\\"]/g, m => (m === '\\' ? '\\\\' : '\\"'));
    }
    isDate(value) {
        if (!value)
            return false;
        const v = value.trim();
        // Strictly match ISO-like date formats to avoid misclassifying plain numbers as dates.
        const isoDate = /^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?$/;
        const isoSlash = /^\d{4}\/\d{2}\/\d{2}$/;
        if (!(isoDate.test(v) || isoSlash.test(v)))
            return false;
        return !isNaN(Date.parse(v));
    }
    isBooleanish(value) {
        const v = (value !== null && value !== void 0 ? value : '').trim().toLowerCase();
        if (!v)
            return false;
        if (v === 'true' || v === 'false')
            return true;
        if (v === 't' || v === 'f')
            return true;
        if (v === 'yes' || v === 'no')
            return true;
        if (v === 'y' || v === 'n')
            return true;
        if (v === 'on' || v === 'off')
            return true;
        if (v === '1' || v === '0')
            return true;
        return false;
    }
    estimateColumnDataType(column) {
        let allBoolean = true, allDate = true, allInteger = true, allFloat = true, allEmpty = true;
        for (const cell of column) {
            const items = cell.split(',').map(item => item.trim());
            for (const item of items) {
                if (item === '')
                    continue;
                allEmpty = false;
                if (!this.isBooleanish(item))
                    allBoolean = false;
                if (!this.isDate(item))
                    allDate = false;
                const num = Number(item);
                if (!Number.isInteger(num))
                    allInteger = false;
                if (isNaN(num))
                    allFloat = false;
            }
        }
        if (allEmpty)
            return "empty";
        if (allBoolean)
            return "boolean";
        if (allDate)
            return "date";
        if (allInteger)
            return "integer";
        if (allFloat)
            return "float";
        return "string";
    }
    getColumnColor(type, isDark, columnIndex, palette = 'default') {
        let hueRange = 0, isDefault = false;
        if (palette === 'cool') {
            switch (type) {
                case "boolean":
                    hueRange = 160;
                    break;
                case "date":
                    hueRange = 210;
                    break;
                case "float":
                    hueRange = isDark ? 195 : 205;
                    break;
                case "integer":
                    hueRange = 130;
                    break;
                case "string":
                    hueRange = 190;
                    break;
                case "empty":
                    isDefault = true;
                    break;
            }
        }
        else if (palette === 'warm') {
            switch (type) {
                case "boolean":
                    hueRange = 55;
                    break;
                case "date":
                    hueRange = 28;
                    break;
                case "float":
                    hueRange = isDark ? 18 : 24;
                    break;
                case "integer":
                    hueRange = 42;
                    break;
                case "string":
                    hueRange = 8;
                    break;
                case "empty":
                    isDefault = true;
                    break;
            }
        }
        else {
            switch (type) {
                case "boolean":
                    hueRange = 30;
                    break;
                case "date":
                    hueRange = 210;
                    break;
                case "float":
                    hueRange = isDark ? 60 : 270;
                    break;
                case "integer":
                    hueRange = 120;
                    break;
                case "string":
                    hueRange = 0;
                    break;
                case "empty":
                    isDefault = true;
                    break;
            }
        }
        if (isDefault)
            return isDark ? "#BBB" : "#444";
        const saturationOffset = ((columnIndex * 7) % 31) - 15;
        const saturation = saturationOffset + (isDark ? 60 : 80);
        const lightnessOffset = ((columnIndex * 13) % 31) - 15;
        const lightness = lightnessOffset + (isDark ? 70 : 30);
        const hueOffset = ((columnIndex * 17) % 31) - 15;
        const finalHue = (hueRange + hueOffset + 360) % 360;
        return this.hslToHex(finalHue, saturation, lightness);
    }
    hslToHex(h, s, l) {
        s /= 100;
        l /= 100;
        const k = (n) => (n + h / 30) % 12;
        const a = s * Math.min(l, 1 - l);
        const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, 9 - k(n), 1));
        const r = Math.round(255 * f(0));
        const g = Math.round(255 * f(8));
        const b = Math.round(255 * f(4));
        return "#" + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('');
    }
    getNonce() {
        let text = '';
        const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        for (let i = 0; i < 32; i++) {
            text += possible.charAt(Math.floor(Math.random() * possible.length));
        }
        return text;
    }
    trimTrailingEmptyRows(rows) {
        const isEmpty = (r) => {
            var _a;
            if (!r || r.length === 0)
                return true;
            for (let i = 0; i < r.length; i++) {
                if (((_a = r[i]) !== null && _a !== void 0 ? _a : '') !== '')
                    return false;
            }
            return true;
        };
        let end = rows.length;
        while (end > 0 && isEmpty(rows[end - 1])) {
            end--;
        }
        return rows.slice(0, end);
    }
}
// Note: Global registry lives on CsvEditorProvider (wrapper)
CsvEditorController.BYTES_PER_MB = 1024 * 1024;
CsvEditorController.DEFAULT_MAX_FILE_SIZE_MB = 10;
CsvEditorController.LARGE_FILE_CONTINUE_THIS_TIME = 'Continue This Time';
CsvEditorController.LARGE_FILE_IGNORE_FOREVER = 'Ignore Forever';
// Wrapper provider: one instance registered with VS Code.
class CsvEditorProvider {
    static normalizeExtension(rawExt) {
        const trimmed = (rawExt !== null && rawExt !== void 0 ? rawExt : '').trim().toLowerCase();
        if (!trimmed)
            return '';
        return trimmed.startsWith('.') ? trimmed : `.${trimmed}`;
    }
    static normalizeSeparator(rawSep) {
        if (typeof rawSep !== 'string')
            return undefined;
        if (rawSep.length === 0)
            return undefined;
        if (rawSep === '\\t')
            return '\t';
        return rawSep;
    }
    static getSeparatorSettings(uri) {
        var _a;
        const fallback = {
            mode: CsvEditorProvider.DEFAULT_SEPARATOR_MODE,
            defaultSeparator: CsvEditorProvider.DEFAULT_SEPARATOR,
            byExtension: { ...CsvEditorProvider.BUILTIN_SEPARATORS_BY_EXTENSION }
        };
        const workspaceAny = vscode.workspace;
        if (!workspaceAny || typeof workspaceAny.getConfiguration !== 'function') {
            return fallback;
        }
        const cfg = workspaceAny.getConfiguration('csv', uri);
        const rawMode = cfg.get('separatorMode', CsvEditorProvider.DEFAULT_SEPARATOR_MODE);
        const mode = rawMode === 'auto' || rawMode === 'default' || rawMode === 'extension'
            ? rawMode
            : CsvEditorProvider.DEFAULT_SEPARATOR_MODE;
        const defaultSeparator = (_a = CsvEditorProvider.normalizeSeparator(cfg.get('defaultSeparator', CsvEditorProvider.DEFAULT_SEPARATOR))) !== null && _a !== void 0 ? _a : CsvEditorProvider.DEFAULT_SEPARATOR;
        const byExtension = {
            ...CsvEditorProvider.BUILTIN_SEPARATORS_BY_EXTENSION
        };
        const rawMap = cfg.get('separatorByExtension', {});
        if (rawMap && typeof rawMap === 'object') {
            for (const [rawExt, rawSep] of Object.entries(rawMap)) {
                const ext = CsvEditorProvider.normalizeExtension(rawExt);
                const sep = CsvEditorProvider.normalizeSeparator(rawSep);
                if (!ext || !sep)
                    continue;
                byExtension[ext] = sep;
            }
        }
        return { mode, defaultSeparator, byExtension };
    }
    static serializeSeparatorSettings(settings) {
        const sortedMapEntries = Object.entries(settings.byExtension)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([ext, sep]) => `${ext}:${sep}`)
            .join('|');
        return `${settings.mode}::${settings.defaultSeparator}::${sortedMapEntries}`;
    }
    static resolveSeparatorFromExtension(filePath, settings) {
        var _a;
        const ext = CsvEditorProvider.normalizeExtension(path.extname((filePath !== null && filePath !== void 0 ? filePath : '').toLowerCase()));
        if (!ext)
            return settings.defaultSeparator;
        return (_a = settings.byExtension[ext]) !== null && _a !== void 0 ? _a : settings.defaultSeparator;
    }
    static countDelimiterOutsideQuotes(line, delimiter) {
        if (!delimiter)
            return 0;
        let inQuotes = false;
        let count = 0;
        for (let i = 0; i < line.length; i++) {
            const ch = line[i];
            if (ch === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    i++;
                    continue;
                }
                inQuotes = !inQuotes;
                continue;
            }
            if (!inQuotes && line.startsWith(delimiter, i)) {
                count++;
                i += delimiter.length - 1;
            }
        }
        return count;
    }
    static detectSeparatorFromText(text, candidates) {
        var _a, _b;
        if (!text)
            return undefined;
        const sampleText = text.length > 300000 ? text.slice(0, 300000) : text;
        const allLines = sampleText.split(/\r\n|\n|\r/);
        const lines = [];
        for (const line of allLines) {
            if (line.trim().length === 0)
                continue;
            lines.push(line);
            if (lines.length >= 200)
                break;
        }
        if (lines.length === 0)
            return undefined;
        const minRowsWithDelimiter = lines.length === 1 ? 1 : 2;
        let best;
        for (const separator of candidates) {
            if (!separator)
                continue;
            const counts = lines.map(line => CsvEditorProvider.countDelimiterOutsideQuotes(line, separator));
            const withDelimiter = counts.filter(count => count > 0);
            if (withDelimiter.length < minRowsWithDelimiter)
                continue;
            const frequencies = new Map();
            for (const count of withDelimiter) {
                frequencies.set(count, ((_a = frequencies.get(count)) !== null && _a !== void 0 ? _a : 0) + 1);
            }
            let modeRowCount = 0;
            for (const freq of frequencies.values()) {
                if (freq > modeRowCount)
                    modeRowCount = freq;
            }
            const consistency = withDelimiter.length > 0 ? modeRowCount / withDelimiter.length : 0;
            const avgDelimiterCount = withDelimiter.reduce((sum, count) => sum + count, 0) / withDelimiter.length;
            const firstLineBonus = ((_b = counts[0]) !== null && _b !== void 0 ? _b : 0) > 0 ? 25 : -25;
            const score = withDelimiter.length * 10 + consistency * 100 + avgDelimiterCount + firstLineBonus;
            const candidate = { separator, rowsWithDelimiter: withDelimiter.length, consistency, avgDelimiterCount, score };
            if (!best) {
                best = candidate;
                continue;
            }
            if (candidate.score > best.score) {
                best = candidate;
                continue;
            }
            if (candidate.score === best.score && candidate.rowsWithDelimiter > best.rowsWithDelimiter) {
                best = candidate;
            }
        }
        return best === null || best === void 0 ? void 0 : best.separator;
    }
    static resolveInheritedSeparator(filePath, text, settings) {
        var _a;
        const extensionSeparator = CsvEditorProvider.resolveSeparatorFromExtension(filePath, settings);
        if (settings.mode === 'default') {
            return settings.defaultSeparator;
        }
        if (settings.mode === 'auto') {
            const candidates = [];
            const seen = new Set();
            const push = (value) => {
                if (!value || seen.has(value))
                    return;
                seen.add(value);
                candidates.push(value);
            };
            push(extensionSeparator);
            push(settings.defaultSeparator);
            CsvEditorProvider.AUTO_SEPARATOR_CANDIDATES.forEach(push);
            Object.values(settings.byExtension).forEach(push);
            return (_a = CsvEditorProvider.detectSeparatorFromText(text, candidates)) !== null && _a !== void 0 ? _a : extensionSeparator;
        }
        return extensionSeparator;
    }
    static parseCsvFieldSpans(text, delimiter) {
        const sep = delimiter && delimiter.length ? delimiter : CsvEditorProvider.DEFAULT_SEPARATOR;
        const rows = [];
        let row = [];
        let fieldStart = 0;
        let i = 0;
        let inQuotes = false;
        let quoted = false;
        const pushField = (end) => {
            row.push({ start: fieldStart, end, quoted });
            quoted = false;
        };
        const pushRow = () => {
            rows.push(row);
            row = [];
        };
        while (i < text.length) {
            if (!inQuotes) {
                if (text.startsWith(sep, i)) {
                    pushField(i);
                    i += sep.length;
                    fieldStart = i;
                    continue;
                }
                const ch = text[i];
                if (ch === '"' && i === fieldStart) {
                    inQuotes = true;
                    quoted = true;
                    i++;
                    continue;
                }
                if (ch === '\r' || ch === '\n') {
                    pushField(i);
                    pushRow();
                    if (ch === '\r' && i + 1 < text.length && text[i + 1] === '\n') {
                        i += 2;
                    }
                    else {
                        i++;
                    }
                    fieldStart = i;
                    continue;
                }
                i++;
                continue;
            }
            if (text[i] === '"') {
                if (i + 1 < text.length && text[i + 1] === '"') {
                    i += 2;
                    continue;
                }
                inQuotes = false;
                i++;
                continue;
            }
            i++;
        }
        pushField(text.length);
        pushRow();
        return rows;
    }
    static encodeCsvField(value, delimiter, preferQuoted) {
        const mustQuote = preferQuoted ||
            value.includes('"') ||
            value.includes('\n') ||
            value.includes('\r') ||
            (!!delimiter && value.includes(delimiter));
        if (!mustQuote) {
            return value;
        }
        const escaped = value.replace(/"/g, '""');
        return `"${escaped}"`;
    }
    static applyFieldUpdatesPreservingFormat(text, delimiter, updates) {
        var _a;
        if (!Array.isArray(updates) || updates.length === 0) {
            return text;
        }
        const deduped = new Map();
        for (const update of updates) {
            if (!Number.isInteger(update.row) || update.row < 0 || !Number.isInteger(update.col) || update.col < 0) {
                continue;
            }
            deduped.set(`${update.row}:${update.col}`, update);
        }
        if (deduped.size === 0) {
            return text;
        }
        const spans = CsvEditorProvider.parseCsvFieldSpans(text, delimiter);
        const edits = [];
        for (const update of deduped.values()) {
            const span = (_a = spans[update.row]) === null || _a === void 0 ? void 0 : _a[update.col];
            if (!span) {
                return undefined;
            }
            const replacement = CsvEditorProvider.encodeCsvField(update.value, delimiter, span.quoted);
            if (text.slice(span.start, span.end) !== replacement) {
                edits.push({ start: span.start, end: span.end, replacement });
            }
        }
        if (edits.length === 0) {
            return text;
        }
        edits.sort((a, b) => b.start - a.start);
        let output = text;
        for (const edit of edits) {
            output = output.slice(0, edit.start) + edit.replacement + output.slice(edit.end);
        }
        return output;
    }
    constructor(context) {
        this.context = context;
    }
    async resolveCustomTextEditor(document, webviewPanel, _token) {
        console.log(`CSV(reg): creating controller for ${document.uri.toString()}`);
        const controller = new CsvEditorController(this.context);
        // Track active controller
        webviewPanel.onDidChangeViewState(e => {
            if (e.webviewPanel.active) {
                CsvEditorProvider.currentActive = controller;
            }
        });
        await controller.resolveCustomTextEditor(document, webviewPanel, _token);
    }
    static getActiveProvider() {
        return CsvEditorProvider.currentActive || CsvEditorProvider.editors.find(ed => ed.isActive());
    }
    static getHiddenRowsForUri(context, uri) {
        var _a;
        const map = context.workspaceState.get(CsvEditorProvider.hiddenRowsKey, {});
        const n = (_a = map[uri.toString()]) !== null && _a !== void 0 ? _a : 0;
        return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
    }
    static async setHiddenRowsForUri(context, uri, n) {
        const map = { ...(context.workspaceState.get(CsvEditorProvider.hiddenRowsKey, {})) };
        if (!Number.isFinite(n) || n <= 0) {
            delete map[uri.toString()];
        }
        else {
            map[uri.toString()] = Math.floor(n);
        }
        await context.workspaceState.update(CsvEditorProvider.hiddenRowsKey, map);
    }
    static getHeaderForUri(context, uri) {
        var _a;
        const map = context.workspaceState.get(CsvEditorProvider.headerKey, {});
        return (_a = map[uri.toString()]) !== null && _a !== void 0 ? _a : true; // fallback default true
    }
    static hasHeaderOverride(context, uri) {
        const map = context.workspaceState.get(CsvEditorProvider.headerKey, {});
        return Object.prototype.hasOwnProperty.call(map, uri.toString());
    }
    static async setHeaderForUri(context, uri, val) {
        const map = { ...(context.workspaceState.get(CsvEditorProvider.headerKey, {})) };
        map[uri.toString()] = !!val; // always persist explicit override
        await context.workspaceState.update(CsvEditorProvider.headerKey, map);
    }
    static getSerialIndexForUri(context, uri) {
        var _a;
        const map = context.workspaceState.get(CsvEditorProvider.serialKey, {});
        return (_a = map[uri.toString()]) !== null && _a !== void 0 ? _a : true; // default true
    }
    static async setSerialIndexForUri(context, uri, val) {
        const map = { ...(context.workspaceState.get(CsvEditorProvider.serialKey, {})) };
        map[uri.toString()] = !!val; // always persist explicit override
        await context.workspaceState.update(CsvEditorProvider.serialKey, map);
    }
    static getSeparatorForUri(context, uri) {
        const map = context.workspaceState.get(CsvEditorProvider.sepKey, {});
        return map[uri.toString()];
    }
    static async setSeparatorForUri(context, uri, sep) {
        const map = { ...(context.workspaceState.get(CsvEditorProvider.sepKey, {})) };
        if (!sep || sep.length === 0) {
            delete map[uri.toString()];
        }
        else {
            map[uri.toString()] = sep;
        }
        await context.workspaceState.update(CsvEditorProvider.sepKey, map);
    }
}
exports.CsvEditorProvider = CsvEditorProvider;
CsvEditorProvider.viewType = 'csv.editor';
CsvEditorProvider.editors = [];
CsvEditorProvider.hiddenRowsKey = 'csv.hiddenRows';
CsvEditorProvider.headerKey = 'csv.headerByUri';
CsvEditorProvider.serialKey = 'csv.serialIndexByUri';
CsvEditorProvider.sepKey = 'csv.separatorByUri';
CsvEditorProvider.DEFAULT_SEPARATOR = ',';
CsvEditorProvider.DEFAULT_SEPARATOR_MODE = 'extension';
CsvEditorProvider.BUILTIN_SEPARATORS_BY_EXTENSION = {
    '.csv': ',',
    '.tsv': '\t',
    '.tab': '\t',
    '.psv': '|'
};
CsvEditorProvider.AUTO_SEPARATOR_CANDIDATES = [',', ';', '\t', '|'];
// Test helpers to access internal utilities without VS Code runtime
CsvEditorProvider.__test = {
    // Pure helper mirroring sort behavior; returns combined rows after sort.
    sortByColumn(rows, index, ascending, treatHeader, hiddenRows) {
        // Trim trailing empty rows like runtime before sorting
        const isEmpty = (r) => {
            var _a;
            if (!r || r.length === 0)
                return true;
            for (let i = 0; i < r.length; i++) {
                if (((_a = r[i]) !== null && _a !== void 0 ? _a : '') !== '')
                    return false;
            }
            return true;
        };
        let end = rows.length;
        while (end > 0 && isEmpty(rows[end - 1])) {
            end--;
        }
        const trimmed = rows.slice(0, end);
        const offset = Math.min(Math.max(0, hiddenRows), trimmed.length);
        let header = [];
        let body = [];
        if (treatHeader && offset < trimmed.length) {
            header = trimmed[offset];
            body = trimmed.slice(offset + 1);
        }
        else {
            body = trimmed.slice(offset);
        }
        const isDateStr = (v) => {
            const s = (v !== null && v !== void 0 ? v : '').trim();
            if (!s)
                return false;
            const isoDate = /^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?$/;
            const isoSlash = /^\d{4}\/\d{2}\/\d{2}$/;
            return isoDate.test(s) || isoSlash.test(s);
        };
        const cmp = (a, b) => {
            const sa = (a !== null && a !== void 0 ? a : '').trim();
            const sb = (b !== null && b !== void 0 ? b : '').trim();
            const aEmpty = sa === '';
            const bEmpty = sb === '';
            if (aEmpty && bEmpty)
                return 0;
            if (aEmpty)
                return 1; // empty sorts last
            if (bEmpty)
                return -1;
            if (isDateStr(sa) && isDateStr(sb)) {
                const da = Date.parse(sa);
                const db = Date.parse(sb);
                if (!isNaN(da) && !isNaN(db))
                    return da - db;
            }
            const na = parseFloat(sa), nb = parseFloat(sb);
            if (!isNaN(na) && !isNaN(nb))
                return na - nb;
            return sa.localeCompare(sb, undefined, { sensitivity: 'base' });
        };
        body.sort((r1, r2) => {
            var _a, _b;
            const diff = cmp((_a = r1[index]) !== null && _a !== void 0 ? _a : '', (_b = r2[index]) !== null && _b !== void 0 ? _b : '');
            return ascending ? diff : -diff;
        });
        const prefix = trimmed.slice(0, offset);
        // Apply same sanitation used before unparse in runtime path
        const combined = (treatHeader ? [...prefix, header, ...body] : [...prefix, ...body]).map(r => r.map((v) => {
            if (v === undefined || v === null)
                return '';
            const t = typeof v;
            if (t === 'number')
                return Number.isNaN(v) ? '' : String(v);
            const s = String(v);
            return s.toLowerCase() === 'nan' ? '' : s;
        }));
        return combined;
    },
    computeColumnWidths(data) {
        const c = new CsvEditorController({});
        return c.computeColumnWidths(data);
    },
    reorderIndexOrder(length, indices, beforeIndex) {
        const c = new CsvEditorController({});
        const n = Number.isFinite(length) ? Math.max(0, Math.trunc(length)) : 0;
        const base = Array.from({ length: n }, (_, i) => i);
        const result = c.reorderByIndices(base, indices, beforeIndex);
        return result.reordered;
    },
    reorderRows(rows, indices, beforeIndex) {
        const c = new CsvEditorController({});
        const result = c.reorderByIndices(rows, indices, beforeIndex);
        return result.reordered;
    },
    reorderColumns(rows, indices, beforeIndex) {
        const c = new CsvEditorController({});
        const numColumns = rows.reduce((max, row) => Math.max(max, row.length), 0);
        const sourceOrder = Array.from({ length: numColumns }, (_, i) => i);
        const orderResult = c.reorderByIndices(sourceOrder, indices, beforeIndex);
        return rows.map((row) => {
            const normalized = Array.from({ length: numColumns }, (_, i) => { var _a; return (_a = row[i]) !== null && _a !== void 0 ? _a : ''; });
            const next = orderResult.reordered.map((colIdx) => { var _a; return (_a = normalized[colIdx]) !== null && _a !== void 0 ? _a : ''; });
            while (next.length > 0 && next[next.length - 1] === '') {
                next.pop();
            }
            return next;
        });
    },
    mutateDataForEdit(data, row, col, value) {
        const c = new CsvEditorController({});
        return c.mutateDataForEdit(data, row, col, value);
    },
    isDate(v) {
        const c = new CsvEditorController({});
        return c.isDate(v);
    },
    estimateColumnDataType(col) {
        const c = new CsvEditorController({});
        return c.estimateColumnDataType(col);
    },
    getColumnColor(t, dark, i, palette = 'default') {
        const c = new CsvEditorController({});
        return c.getColumnColor(t, dark, i, palette);
    },
    resolveEffectiveColumnColorMode(baseMode, isDiffContext, diffUseThemeForeground) {
        return CsvEditorController.resolveEffectiveColumnColorMode(baseMode, isDiffContext, diffUseThemeForeground);
    },
    resolveEffectiveFontSize(csvFontSize, editorFontSize) {
        return CsvEditorController.resolveEffectiveFontSize(csvFontSize, editorFontSize);
    },
    hslToHex(h, s, l) {
        const c = new CsvEditorController({});
        return c.hslToHex(h, s, l);
    },
    formatCellContent(text, linkify) {
        const c = new CsvEditorController({});
        return c.formatCellContent(text, linkify);
    },
    isAllowedExternalUrl(url) {
        const c = new CsvEditorController({});
        return c.isAllowedExternalUrl(url);
    },
    shouldPromptForLargeFile(fileSizeBytes, maxFileSizeMB) {
        const c = new CsvEditorController({});
        return c.shouldPromptForLargeFile(fileSizeBytes, maxFileSizeMB);
    },
    // Expose header heuristic for tests. Allows specifying hiddenRows and
    // optionally an override value through a mock workspaceState.
    getEffectiveHeader(data, hiddenRows, override = undefined) {
        const c = new CsvEditorController({});
        // Minimal fake URI and context to satisfy header-override checks
        const fakeUri = { toString: () => 'vscode-test://csv/fixture', fsPath: '/csv/fixture.csv' };
        const state = {};
        if (override !== undefined) {
            state[CsvEditorProvider.headerKey] = { [fakeUri.toString()]: override };
        }
        c.context = {
            workspaceState: {
                get: (key, def) => (key in state ? state[key] : def),
                update: async (key, val) => { state[key] = val; }
            }
        };
        c.document = { uri: fakeUri };
        return c.getEffectiveHeader(data, hiddenRows);
    },
    // Compute the effective separator used for a given file path with optional override.
    getEffectiveSeparator(filePath, override, options) {
        var _a, _b, _c;
        if (override && override.length) {
            return override;
        }
        const mode = (_a = options === null || options === void 0 ? void 0 : options.mode) !== null && _a !== void 0 ? _a : 'extension';
        const defaultSeparator = (_b = CsvEditorProvider.normalizeSeparator(options === null || options === void 0 ? void 0 : options.defaultSeparator)) !== null && _b !== void 0 ? _b : CsvEditorProvider.DEFAULT_SEPARATOR;
        const byExtension = { ...CsvEditorProvider.BUILTIN_SEPARATORS_BY_EXTENSION };
        if (options === null || options === void 0 ? void 0 : options.byExtension) {
            for (const [rawExt, rawSep] of Object.entries(options.byExtension)) {
                const ext = CsvEditorProvider.normalizeExtension(rawExt);
                const sep = CsvEditorProvider.normalizeSeparator(rawSep);
                if (!ext || !sep)
                    continue;
                byExtension[ext] = sep;
            }
        }
        const text = (_c = options === null || options === void 0 ? void 0 : options.text) !== null && _c !== void 0 ? _c : '';
        return CsvEditorProvider.resolveInheritedSeparator(filePath, text, {
            mode,
            defaultSeparator,
            byExtension
        });
    },
    applyFieldUpdatesPreservingFormat(text, delimiter, updates) {
        return CsvEditorProvider.applyFieldUpdatesPreservingFormat(text, delimiter, updates);
    },
    computePastePlan(matrix, anchorRow, anchorCol, selection) {
        return CsvEditorController.computePastePlan(matrix, anchorRow, anchorCol, selection);
    },
    applyPasteMatrixToData(data, matrix, anchorRow, anchorCol, selection) {
        return CsvEditorController.applyPasteMatrixToData(data, matrix, anchorRow, anchorCol, selection);
    },
    // Expose chunking/table generation for large-data tests. Returns parsed chunk count.
    generateTableChunksMeta(data, treatHeader, addSerialIndex, hiddenRows, clickableLinks = true, columnColorMode = 'type', columnColorPalette = 'default', showTrailingEmptyRow = true) {
        const c = new CsvEditorController({});
        const result = c.generateTableAndChunks(data, treatHeader, addSerialIndex, hiddenRows, clickableLinks, columnColorMode, columnColorPalette, showTrailingEmptyRow);
        try {
            const chunks = JSON.parse(result.chunksJson);
            return { chunkCount: Array.isArray(chunks) ? chunks.length : 0, hasTable: typeof result.tableHtml === 'string' && result.tableHtml.includes('<table') };
        }
        catch {
            return { chunkCount: 0, hasTable: false };
        }
    },
    generateTableAndChunksRaw(data, treatHeader, addSerialIndex, hiddenRows, clickableLinks = true, columnColorMode = 'type', columnColorPalette = 'default', showTrailingEmptyRow = true) {
        const c = new CsvEditorController({});
        const result = c.generateTableAndChunks(data, treatHeader, addSerialIndex, hiddenRows, clickableLinks, columnColorMode, columnColorPalette, showTrailingEmptyRow);
        let chunks = [];
        try {
            chunks = JSON.parse(result.chunksJson);
        }
        catch { }
        return { tableHtml: result.tableHtml, chunks };
    },
    generateRuntimeChunkTransport(data, treatHeader, addSerialIndex, hiddenRows, start = undefined) {
        const c = new CsvEditorController({});
        const result = c.generateTableAndChunks(data, treatHeader, addSerialIndex, hiddenRows, 
        /* clickableLinks */ true, 
        /* columnColorMode */ 'type', 
        /* columnColorPalette */ 'default', 
        /* showTrailingEmptyRow */ true, 
        /* maxSerializedChunks */ 0);
        let chunks = [];
        try {
            chunks = JSON.parse(result.chunksJson);
        }
        catch { }
        const out = {
            serializedChunkCount: chunks.length,
            nextChunkStart: result.nextChunkStart,
            hasRemoteChunks: result.hasRemoteChunks,
            hasChunkState: !!result.chunkState
        };
        if (typeof start === 'number' && result.chunkState) {
            const response = c.renderChunkFromState(result.chunkState, start);
            out.response = {
                html: response.html,
                nextStart: response.nextStart,
                done: response.done
            };
        }
        return out;
    }
};
