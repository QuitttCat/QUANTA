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
Object.defineProperty(exports, "__esModule", { value: true });
exports.deactivate = exports.activate = void 0;
const vscode = __importStar(require("vscode"));
const CsvEditorProvider_1 = require("./CsvEditorProvider");
const commands_1 = require("./commands");
function activate(context) {
    console.log('CSV: Extension activated');
    // Commands (toggle features, change separator/font)
    (0, commands_1.registerCsvCommands)(context);
    // Auto-refresh all open CSV editors when relevant CSV settings change
    const cfgListener = vscode.workspace.onDidChangeConfiguration(e => {
        // If the user turned the extension on, immediately upgrade open CSV/TSV tabs
        if (e.affectsConfiguration('csv.enabled')) {
            const enabled = vscode.workspace.getConfiguration('csv').get('enabled', true);
            console.log(`[CSV(enable)]: configuration changed -> enabled=${enabled}`);
            if (enabled) {
                const candidates = [];
                const groups = vscode.window.tabGroups.all;
                console.log(`[CSV(enable)]: scanning ${groups.length} tab group(s)`);
                groups.forEach((group, gi) => {
                    console.log(`[CSV(enable)]: group[${gi}] has ${group.tabs.length} tab(s)`);
                    group.tabs.forEach((tab, ti) => {
                        var _a, _b;
                        const input = tab.input;
                        const viewType = input === null || input === void 0 ? void 0 : input.viewType;
                        const uri = (input === null || input === void 0 ? void 0 : input.uri) instanceof vscode.Uri ? input.uri : undefined;
                        const path = (uri === null || uri === void 0 ? void 0 : uri.fsPath) || '(no-uri)';
                        console.log(`[CSV(enable)]: group[${gi}] tab[${ti}] vt=${viewType !== null && viewType !== void 0 ? viewType : '(text?)'} uri=${path} active=${tab.isActive} preview=${tab.isPreview}`);
                        if (!input)
                            return;
                        if (viewType === CsvEditorProvider_1.CsvEditorProvider.viewType)
                            return; // already our editor
                        if (!uri)
                            return;
                        const fsPath = ((_b = (_a = uri.fsPath) === null || _a === void 0 ? void 0 : _a.toLowerCase) === null || _b === void 0 ? void 0 : _b.call(_a)) || '';
                        const isCsvLike = fsPath.endsWith('.csv') || fsPath.endsWith('.tsv') || fsPath.endsWith('.tab') || fsPath.endsWith('.psv');
                        console.log(`[CSV(enable)]: -> eligible=${isCsvLike}`);
                        if (!isCsvLike)
                            return;
                        candidates.push({ group, groupIndex: gi, tab, tabIndex: ti, uri, wasActive: tab.isActive, wasPreview: tab.isPreview, viewColumn: group.viewColumn });
                    });
                });
                console.log(`[CSV(enable)]: candidates=${candidates.length}`);
                (async () => {
                    const processed = new Set();
                    for (const c of candidates) {
                        try {
                            console.log(`[CSV(enable)]: closing group[${c.groupIndex}] tab[${c.tabIndex}] uri=${c.uri.fsPath}`);
                            await vscode.window.tabGroups.close(c.tab);
                        }
                        catch (err) {
                            console.error(`[CSV(enable)]: close failed for ${c.uri.fsPath}`, err);
                        }
                        try {
                            const openOpts = { viewColumn: c.viewColumn, preserveFocus: !c.wasActive, preview: c.wasPreview };
                            console.log(`[CSV(enable)]: opening custom editor for ${c.uri.fsPath} in column=${c.viewColumn}`);
                            await vscode.commands.executeCommand('vscode.openWith', c.uri, CsvEditorProvider_1.CsvEditorProvider.viewType, openOpts);
                            processed.add(c.uri.toString());
                        }
                        catch (err) {
                            console.error(`[CSV(enable)]: openWith failed for ${c.uri.fsPath}`, err);
                        }
                    }
                    // Final sweep: ensure no stale non-custom tabs remain for processed URIs across all groups
                    try {
                        const stale = [];
                        vscode.window.tabGroups.all.forEach((g, gi) => {
                            g.tabs.forEach((t, ti) => {
                                const inp = t.input;
                                const vt = inp === null || inp === void 0 ? void 0 : inp.viewType;
                                const u = (inp === null || inp === void 0 ? void 0 : inp.uri) instanceof vscode.Uri ? inp.uri : undefined;
                                const key = u === null || u === void 0 ? void 0 : u.toString();
                                if (key && processed.has(key) && vt !== CsvEditorProvider_1.CsvEditorProvider.viewType) {
                                    console.log(`[CSV(enable)]: final-sweep closing group[${gi}] tab[${ti}] uri=${u === null || u === void 0 ? void 0 : u.fsPath} vt=${vt}`);
                                    stale.push(t);
                                }
                            });
                        });
                        if (stale.length) {
                            await vscode.window.tabGroups.close(stale);
                        }
                    }
                    catch (err) {
                        console.error('[CSV(enable)]: final-sweep error', err);
                    }
                    console.log(`[CSV(enable)]: done processing ${candidates.length} candidate(s)`);
                })();
            }
        }
        const keys = [
            'csv.fontFamily',
            'csv.cellPadding',
            'csv.columnColorMode',
            'csv.columnColorPalette',
            'csv.diffUseThemeForeground',
            'csv.clickableLinks',
            'csv.showTrailingEmptyRow',
            'csv.separatorMode',
            'csv.defaultSeparator',
            'csv.separatorByExtension'
        ];
        const changed = keys.filter(k => e.affectsConfiguration(k));
        if (changed.length) {
            CsvEditorProvider_1.CsvEditorProvider.editors.forEach(ed => ed.refresh());
        }
    });
    context.subscriptions.push(cfgListener);
    // Register the custom editor provider for CSV/TSV
    context.subscriptions.push(vscode.window.registerCustomEditorProvider(CsvEditorProvider_1.CsvEditorProvider.viewType, new CsvEditorProvider_1.CsvEditorProvider(context), { supportsMultipleEditorsPerDocument: false }));
}
exports.activate = activate;
function deactivate() {
    console.log('CSV: Extension deactivated');
}
exports.deactivate = deactivate;
