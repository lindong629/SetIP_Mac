#import <Cocoa/Cocoa.h>
#import <QuartzCore/QuartzCore.h>

// 版本号由 build_app.sh 从 Info.plist 注入；单独编译测试时回退到 2.18。
#ifndef SETIP_VERSION
#define SETIP_VERSION "2.18"
#endif

// SetIP 原生宿主窗口：直接在 App 内运行 SetIP-bin，不再借 Terminal。
// 进程退出（输入 q）后自动结束 App，Dock 里不会残留终端图标或窗口。
// 视觉：深色主题（对标 WorkBuddy），高对比文字 + 圆角卡片 + 徽章。

// 顶部对齐的内容画布：从视图顶端逐行绘制富文本，短内容不会像 NSTextView 那样垂直居中悬空。
@interface SetIPCanvas : NSView
@property (strong, nonatomic) NSAttributedString *content;
@end
@implementation SetIPCanvas
- (void)setContent:(NSAttributedString *)content {
    _content = content;
    [self setNeedsDisplay:YES];
}
- (void)drawRect:(NSRect)dirtyRect {
    if (self.content) [self.content drawInRect:self.bounds];
}
@end

@interface AppDelegate : NSObject <NSApplicationDelegate, NSWindowDelegate, NSTextFieldDelegate>
@property (strong, nonatomic) NSWindow *window;
@property (strong, nonatomic) NSView *headerView;
@property (strong, nonatomic) NSView *footerView;
@property (strong, nonatomic) NSView *cardView;
// 固定仪表盘：四个槽位坐标只由窗口尺寸决定，与内容无关；步骤切换时框架纹丝不动。
@property (strong, nonatomic) NSView *netWrap, *statusWrap, *configWrap, *actionWrap;
@property (strong, nonatomic) SetIPCanvas *netView, *statusView, *configView, *actionView;
@property (strong, nonatomic) NSTextView *hintBar;
@property (nonatomic) CGFloat hintHeight;
// 跨步骤缓存：信息面板（网卡/配置）常驻，状态/操作面板按屏更新
@property (strong, nonatomic) NSArray<NSString *> *cachedNet;
@property (strong, nonatomic) NSArray<NSString *> *cachedStatus;
@property (strong, nonatomic) NSArray<NSString *> *cachedConfig;
@property (strong, nonatomic) NSArray<NSString *> *cachedAction;
@property (nonatomic) BOOL compactRendering; // 槽位内使用紧凑行距
@property (strong, nonatomic) NSTextField *input;
@property (strong, nonatomic) NSButton *homeButton;
@property (strong, nonatomic) CAGradientLayer *headerGradient;
@property (strong, nonatomic) NSTask *task;
@property (strong, nonatomic) NSPipe *stdinPipe;
@property (strong, nonatomic) NSMutableString *raw;
// 方向键选择：从当前屏的 adapter/menu token 提取可选项
@property (strong, nonatomic) NSArray<NSDictionary *> *selectOptions; // 每项 @{@"key":token首字段, @"value":要提交给Python的值}
@property (nonatomic) NSInteger selectedIndex;   // -1 = 未用方向键选中（保持空回车默认行为）
@property (nonatomic) BOOL settingSelectionProgrammatically; // 程序化填入选中值时跳过"手动输入取消高亮"
@property (nonatomic) NSUInteger lastClearFrom;  // 换屏检测：清屏位置变化时重置选中态
- (void)layoutSubviews;
@end

// ------------------------------------------------------------ 深色主题配色 --
static NSColor *SetIPHex(NSString *hex) {
    unsigned int rgb = 0;
    [[NSScanner scannerWithString:hex] scanHexInt:&rgb];
    return [NSColor colorWithCalibratedRed:((rgb >> 16) & 0xFF) / 255.0
                                     green:((rgb >> 8) & 0xFF) / 255.0
                                      blue:(rgb & 0xFF) / 255.0
                                     alpha:1.0];
}

// 窗口背景 / 卡片
static NSColor *SetIPBg(void)       { return SetIPHex(@"17181C"); } // 窗口底色
static NSColor *SetIPCard(void)     { return SetIPHex(@"212229"); } // 内容卡片
static NSColor *SetIPCardEdge(void) { return SetIPHex(@"30323C"); } // 卡片描边
static NSColor *SetIPFooter(void)   { return SetIPHex(@"1B1C21"); } // 输入条
// 文字（高对比，深色底上清晰）
static NSColor *SetIPInk(void)  { return SetIPHex(@"F4F5F7"); } // 主文字
static NSColor *SetIPSub(void)  { return SetIPHex(@"D3D7DE"); } // 次级文字
static NSColor *SetIPGrey(void) { return SetIPHex(@"A6ACB8"); } // 次要/提示
// 主题色
static NSColor *SetIPBlue(void)   { return SetIPHex(@"6BA6FA"); }
static NSColor *SetIPGreen(void)  { return SetIPHex(@"57D98E"); }
static NSColor *SetIPRed(void)    { return SetIPHex(@"F87C74"); }
static NSColor *SetIPPurple(void) { return SetIPHex(@"C39AF5"); }
static NSColor *SetIPTeal(void)   { return SetIPHex(@"57D3DF"); }
static NSColor *SetIPAmber(void)  { return SetIPHex(@"ECC069"); }
// 徽章底色
static NSColor *SetIPChipBlue(void)  { return SetIPHex(@"27385C"); }
static NSColor *SetIPChipGreen(void) { return SetIPHex(@"1F4A38"); }
static NSColor *SetIPChipRed(void)   { return SetIPHex(@"512D2D"); }
static NSColor *SetIPChipGrey(void)  { return SetIPHex(@"353842"); }

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    // 强制深色外观，保证主题色与配色一致（不随系统浅色模式跳变）
    if (@available(macOS 10.14, *)) {
        [NSApp setAppearance:[NSAppearance appearanceNamed:NSAppearanceNameDarkAqua]];
    }
    [NSApp setActivationPolicy:NSApplicationActivationPolicyRegular];
    [self buildMenu];
    [self buildWindow];
    [self monitorKeys];
    [self.window makeKeyAndOrderFront:nil];
    [self.window makeFirstResponder:self.input];
    [NSApp activateIgnoringOtherApps:YES];
    [self startTask];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return YES;
}

- (void)buildMenu {
    NSMenu *mainMenu = [NSMenu new];
    NSMenuItem *appItem = [[NSMenuItem alloc] initWithTitle:@"SetIP"
                                                     action:nil
                                              keyEquivalent:@""];
    NSMenu *appMenu = [NSMenu new];
    NSMenuItem *home = [[NSMenuItem alloc] initWithTitle:@"返回主界面"
                                                  action:@selector(goHome)
                                           keyEquivalent:@"r"];
    [home setKeyEquivalentModifierMask:NSEventModifierFlagCommand];
    [home setTarget:self];
    [appMenu addItem:home];
    [appMenu addItem:[NSMenuItem separatorItem]];
    NSMenuItem *quit = [[NSMenuItem alloc] initWithTitle:@"退出 SetIP"
                                                  action:@selector(terminate:)
                                           keyEquivalent:@"q"];
    [quit setKeyEquivalentModifierMask:NSEventModifierFlagCommand];
    [appMenu addItem:quit];
    [appItem setSubmenu:appMenu];
    [mainMenu addItem:appItem];
    [NSApp setMainMenu:mainMenu];
}

- (NSTextField *)labelWithString:(NSString *)text frame:(NSRect)frame font:(NSFont *)font color:(NSColor *)color {
    NSTextField *label = [[NSTextField alloc] initWithFrame:frame];
    [label setStringValue:text];
    [label setFont:font];
    [label setTextColor:color];
    [label setBezeled:NO];
    [label setDrawsBackground:NO];
    [label setEditable:NO];
    [label setSelectable:NO];
    return label;
}

- (NSView *)headerViewOfWidth:(CGFloat)width height:(CGFloat)height {
    NSView *bar = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, width, height)];
    [bar setAutoresizingMask:NSViewWidthSizable];
    [bar setWantsLayer:YES];

    CAGradientLayer *grad = [CAGradientLayer layer];
    grad.frame = bar.bounds;
    grad.colors = @[(id)[SetIPHex(@"3B7BF6") CGColor], (id)[SetIPHex(@"2B58D8") CGColor]];
    [bar.layer addSublayer:grad];
    self.headerGradient = grad;

    // 左侧标识圆点
    NSView *dot = [[NSView alloc] initWithFrame:NSMakeRect(18, height / 2 - 5, 10, 10)];
    [dot setWantsLayer:YES];
    dot.layer.cornerRadius = 5;
    dot.layer.backgroundColor = [[NSColor whiteColor] CGColor];
    dot.layer.opacity = 0.95;
    [bar addSubview:dot];

    NSTextField *title = [self labelWithString:@"SetIP  ·  IP 管理器"
                                         frame:NSMakeRect(36, height / 2 - 12, 240, 24)
                                          font:[NSFont systemFontOfSize:15 weight:NSFontWeightSemibold]
                                         color:[NSColor whiteColor]];
    title.autoresizingMask = NSViewMaxXMargin;
    [bar addSubview:title];

    // 一键返回主界面按钮（Esc / Cmd+R 同效）
    NSButton *home = [[NSButton alloc] initWithFrame:NSMakeRect(width - 152, (height - 26) / 2, 76, 26)];
    NSMutableAttributedString *homeTitle =
        [[NSMutableAttributedString alloc] initWithString:@"⌂ 主界面"
            attributes:@{NSFontAttributeName: [NSFont systemFontOfSize:12 weight:NSFontWeightMedium],
                         NSForegroundColorAttributeName: [NSColor whiteColor]}];
    [home setAttributedTitle:homeTitle];
    [home setBordered:NO];
    [home setTarget:self];
    [home setAction:@selector(goHome)];
    [home setToolTip:@"返回主界面（Esc / ⌘R）"];
    [home setAutoresizingMask:NSViewMinXMargin];
    [home setWantsLayer:YES];
    home.layer.backgroundColor = [SetIPHex(@"2C3040") CGColor];
    home.layer.cornerRadius = 6;
    home.layer.borderWidth = 1;
    home.layer.borderColor = [[NSColor whiteColor] colorWithAlphaComponent:0.28].CGColor;
    self.homeButton = home;
    [bar addSubview:home];

    NSString *ver = [NSString stringWithUTF8String:SETIP_VERSION];
    NSTextField *version = [self labelWithString:[NSString stringWithFormat:@"v%@", ver]
                                           frame:NSMakeRect(width - 68, height / 2 - 11, 52, 22)
                                            font:[NSFont systemFontOfSize:12 weight:NSFontWeightMedium]
                                           color:[[NSColor whiteColor] colorWithAlphaComponent:0.9]];
    version.alignment = NSTextAlignmentRight;
    version.autoresizingMask = NSViewMinXMargin;
    [version setTag:1001];
    [bar addSubview:version];
    return bar;
}

- (NSView *)footerViewOfWidth:(CGFloat)width height:(CGFloat)height {
    NSView *bar = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, width, height)];
    [bar setAutoresizingMask:NSViewWidthSizable];
    [bar setWantsLayer:YES];
    bar.layer.backgroundColor = [SetIPFooter() CGColor];

    NSBox *topLine = [[NSBox alloc] initWithFrame:NSMakeRect(0, height - 1, width, 1)];
    [topLine setBoxType:NSBoxSeparator];
    [topLine setAutoresizingMask:NSViewWidthSizable | NSViewMinYMargin];
    [bar addSubview:topLine];

    NSView *inputWrap = [[NSView alloc] initWithFrame:NSMakeRect(16, 10, width - 32, height - 20)];
    [inputWrap setAutoresizingMask:NSViewWidthSizable];
    [inputWrap setWantsLayer:YES];
    inputWrap.layer.backgroundColor = [SetIPCard() CGColor];
    inputWrap.layer.cornerRadius = 8;
    inputWrap.layer.borderWidth = 1;
    inputWrap.layer.borderColor = [SetIPCardEdge() CGColor];

    NSTextField *field = [[NSTextField alloc] initWithFrame:NSMakeRect(10, 0, NSWidth(inputWrap.bounds) - 20, NSHeight(inputWrap.bounds))];
    [field setAutoresizingMask:NSViewWidthSizable];
    [field setFont:[NSFont systemFontOfSize:13]];
    [field setTextColor:SetIPInk()];
    [field setPlaceholderString:@"回车=活动网卡  ·  m=主界面  ·  q=退出"];
    [field setBezeled:NO];
    [field setDrawsBackground:NO];
    [field setFocusRingType:NSFocusRingTypeNone];
    [field setDelegate:self];
    self.input = field;
    [inputWrap addSubview:field];
    [bar addSubview:inputWrap];
    return bar;
}

- (void)layoutSubviews {
    NSRect bounds = self.window.contentView.bounds;
    CGFloat W = NSWidth(bounds), H = NSHeight(bounds);
    CGFloat headerH = 56, footerH = 60, pad = 16, gap = 12;
    [self.headerView setFrame:NSMakeRect(0, H - headerH, W, headerH)];
    [self.footerView setFrame:NSMakeRect(0, 0, W, footerH)];

    CGFloat y = footerH + gap;
    CGFloat h = H - headerH - footerH - gap - pad;
    if (h < 120) h = 120;
    [self.cardView setFrame:NSMakeRect(pad, y, W - pad * 2, h)];

    // 只更新渐变层自身尺寸；切勿遍历所有 sublayer——那会把主界面按钮和圆点的 layer 一起撑满标题栏
    self.headerGradient.frame = self.headerView.bounds;
    // 右侧按钮与版本号贴右排列
    [self.homeButton setFrame:NSMakeRect(W - 152, (headerH - 26) / 2, 76, 26)];
    NSView *version = [self.headerView viewWithTag:1001];
    if (version) [version setFrame:NSMakeRect(W - 68, (headerH - 22) / 2, 52, 22)];

    // 底部输入条随宽度变化：[0]=分隔线 [1]=输入框容器
    NSArray *subs = self.footerView.subviews;
    if (subs.count > 1) {
        NSView *line = subs[0];
        [line setFrame:NSMakeRect(0, footerH - 1, W, 1)];
        NSView *inputWrap = subs[1];
        [inputWrap setFrame:NSMakeRect(16, 10, W - 32, footerH - 20)];
        for (NSView *inner in inputWrap.subviews) {
            [inner setFrame:NSMakeRect(10, 0, NSWidth(inputWrap.bounds) - 20, NSHeight(inputWrap.bounds))];
        }
    }

    [self layoutColumns];
}

// 固定四宫格：坐标只与窗口尺寸有关，绝不随内容变化。槽位空闲时保留上次内容（缓存），
// 因此步骤切换时框架与信息面板纹丝不动，只有「操作」槽内菜单/结果互换。
- (void)layoutColumns {
    NSRect card = self.cardView.bounds;
    CGFloat W = NSWidth(card), H = NSHeight(card);
    CGFloat pad = 14, gap = 12;

    // 底部提示条：始终占据固定高度，避免其出现/消失挤动上方槽位
    CGFloat hintH = self.hintBar.hidden ? 0 : self.hintHeight;
    if (hintH > 30) hintH = 30;
    if (!self.hintBar.hidden) [self.hintBar setFrame:NSMakeRect(pad, 2, W - pad * 2, hintH)];

    CGFloat bottom = pad + (self.hintBar.hidden ? 0 : hintH + 6);
    CGFloat top = H - pad;
    CGFloat availH = top - bottom;
    if (availH < 120) availH = 120;
    CGFloat rowH = (availH - gap) / 2;

    CGFloat innerW = W - pad * 2;
    CGFloat rightW = (innerW - gap) * 0.72;   // 右侧放配置/状态（长行多），给足宽度
    CGFloat leftW = innerW - gap - rightW;
    CGFloat lx = pad, rx = pad + leftW + gap;
    CGFloat yTop = bottom + rowH + gap;

    [self.netWrap    setFrame:NSMakeRect(lx, yTop,  leftW, rowH)];    // 左上：网络服务
    [self.actionWrap setFrame:NSMakeRect(lx, bottom, leftW, rowH)];   // 左下：操作
    [self.statusWrap setFrame:NSMakeRect(rx, yTop,  rightW, rowH)];   // 右上：当前网络状态
    [self.configWrap setFrame:NSMakeRect(rx, bottom, rightW, rowH)];  // 右下：配置模板

    [self placeSlot:self.netWrap    text:self.netView];
    [self placeSlot:self.actionWrap text:self.actionView];
    [self placeSlot:self.statusWrap text:self.statusView];
    [self placeSlot:self.configWrap text:self.configView];
}

// 槽位内部：固定标题条 + 内容视图（坐标固定，不测量文本）
- (void)placeSlot:(NSView *)wrap text:(SetIPCanvas *)cv {
    CGFloat w = NSWidth(wrap.bounds), h = NSHeight(wrap.bounds);
    NSView *cap = [wrap viewWithTag:88];
    if (cap) [cap setFrame:NSMakeRect(12, h - 30, w - 24, 20)];
    [cv setFrame:NSMakeRect(6, 6, w - 12, h - 36)];
}

// 构造一个固定槽位：圆角卡片 + 顶部小标题 + 顶部对齐内容画布（frame 由 layoutColumns 统一设定）
- (NSView *)makeSlotTitle:(NSString *)title outText:(SetIPCanvas **)outText {
    NSView *wrap = [[NSView alloc] initWithFrame:NSZeroRect];
    [wrap setWantsLayer:YES];
    wrap.layer.backgroundColor = [SetIPHex(@"282A31") CGColor];
    wrap.layer.cornerRadius = 10;
    wrap.layer.borderWidth = 1;
    wrap.layer.borderColor = [SetIPCardEdge() CGColor];

    NSTextField *cap = [self labelWithString:title frame:NSZeroRect
                                        font:[self ui:12.5 weight:NSFontWeightSemibold]
                                       color:SetIPBlue()];
    [cap setTag:88];
    [wrap addSubview:cap];

    SetIPCanvas *cv = [[SetIPCanvas alloc] initWithFrame:NSZeroRect];
    [wrap addSubview:cv];
    if (outText) *outText = cv;
    return wrap;
}

- (void)buildWindow {
    NSRect frame = NSMakeRect(0, 0, 1000, 600);
    self.window = [[NSWindow alloc] initWithContentRect:frame
                                              styleMask:(NSWindowStyleMaskTitled |
                                                         NSWindowStyleMaskClosable |
                                                         NSWindowStyleMaskMiniaturizable |
                                                         NSWindowStyleMaskResizable)
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    [self.window setTitle:@"SetIP · IP 管理器"];
    [self.window setMinSize:NSMakeSize(820, 520)];
    [self.window center];
    [self.window setDelegate:self];

    NSView *content = self.window.contentView;
    [content setWantsLayer:YES];
    [content.layer setBackgroundColor:[SetIPBg() CGColor]];

    self.headerView = [self headerViewOfWidth:NSWidth(frame) height:56];
    [content addSubview:self.headerView];
    self.footerView = [self footerViewOfWidth:NSWidth(frame) height:60];
    [content addSubview:self.footerView];

    // 卡片容器（固定框架，尺寸由 layoutSubviews 设定，跨步骤不变）
    NSView *card = [[NSView alloc] initWithFrame:NSZeroRect];
    [card setWantsLayer:YES];
    card.layer.backgroundColor = [SetIPCard() CGColor];
    card.layer.cornerRadius = 12;
    card.layer.borderWidth = 1;
    card.layer.borderColor = [SetIPCardEdge() CGColor];
    self.cardView = card;
    [content addSubview:card];

    // 固定四槽位：位置由 layoutColumns 统一算定，跨步骤不变。
    // 左上=网络服务列表  左下=应用操作区  右上=当前网络状态  右下=配置模板
    SetIPCanvas *netText = nil, *statusText = nil, *configText = nil, *actionText = nil;
    self.netWrap    = [self makeSlotTitle:@"网络服务"     outText:&netText];
    self.statusWrap = [self makeSlotTitle:@"当前网络状态" outText:&statusText];
    self.configWrap = [self makeSlotTitle:@"配置模板"     outText:&configText];
    self.actionWrap = [self makeSlotTitle:@"操作"         outText:&actionText];
    self.netView = netText;
    self.statusView = statusText;
    self.configView = configText;
    self.actionView = actionText;
    [card addSubview:self.netWrap];
    [card addSubview:self.statusWrap];
    [card addSubview:self.configWrap];
    [card addSubview:self.actionWrap];

    self.cachedNet = @[];
    self.cachedStatus = @[];
    self.cachedConfig = @[];
    self.cachedAction = @[];
    self.selectOptions = @[];
    self.selectedIndex = -1;
    self.lastClearFrom = 0;

    // 底部提示条（hint / sub）：横跨卡片、浅色文字，无边框
    NSTextView *hint = [[NSTextView alloc] initWithFrame:NSZeroRect];
    [hint setEditable:NO];
    [hint setSelectable:NO];
    [hint setRichText:NO];
    [hint setDrawsBackground:NO];
    [hint setFont:[self ui:12.5 weight:NSFontWeightRegular]];
    [hint setTextColor:SetIPGrey()];
    [hint setTextContainerInset:NSMakeSize(4, 2)];
    [hint setHidden:YES];
    self.hintBar = hint;
    [card addSubview:hint];

    [self layoutSubviews];
}

- (void)startTask {
    NSString *bin = [[NSBundle mainBundle] pathForAuxiliaryExecutable:@"SetIP-bin"];
    if (!bin) {
        [self appendPlain:@"错误：找不到 SetIP-bin，请重新打包 App。"];
        return;
    }

    NSTask *task = [NSTask new];
    [task setExecutableURL:[NSURL fileURLWithPath:bin]];
    [task setCurrentDirectoryURL:[self executableDir]];

    NSMutableDictionary *env = [[[NSProcessInfo processInfo] environment] mutableCopy];
    env[@"SETIP_COLOR"] = @"never";     // 原生窗口按结构化 token 自行渲染，不需要 ANSI 颜色
    env[@"SETIP_NATIVE"] = @"1";        // 让 Python 输出 \001TYPE\001 结构化指令
    env[@"PYTHONUNBUFFERED"] = @"1";    // 管道不是 tty，强制不缓冲
    [task setEnvironment:env];

    NSPipe *out = [NSPipe pipe];
    NSPipe *err = [NSPipe pipe];
    NSPipe *inPipe = [NSPipe pipe];
    [task setStandardOutput:out];
    [task setStandardError:err];
    [task setStandardInput:inPipe];
    self.stdinPipe = inPipe;

    __weak AppDelegate *weakSelf = self;
    out.fileHandleForReading.readabilityHandler = ^(NSFileHandle *handle) {
        NSData *data = [handle availableData];
        if (data.length) {
            dispatch_async(dispatch_get_main_queue(), ^{ [weakSelf appendData:data]; });
        }
    };
    err.fileHandleForReading.readabilityHandler = ^(NSFileHandle *handle) {
        NSData *data = [handle availableData];
        if (data.length) {
            dispatch_async(dispatch_get_main_queue(), ^{ [weakSelf appendData:data]; });
        }
    };
    task.terminationHandler = ^(NSTask *finished) {
        dispatch_async(dispatch_get_main_queue(), ^{
            [NSApp terminate:nil];
        });
    };

    @try {
        [task launch];
        self.task = task;
    } @catch (NSException *exception) {
        [self appendPlain:[NSString stringWithFormat:@"启动失败: %@\n", exception.reason]];
    }
}

- (NSURL *)executableDir {
    NSString *path = [[NSBundle mainBundle] pathForAuxiliaryExecutable:@"SetIP-bin"];
    return [NSURL fileURLWithPath:[path stringByDeletingLastPathComponent]];
}

- (BOOL)windowShouldClose:(NSWindow *)sender {
    if (self.task && self.task.isRunning) {
        [self.task terminate];
    }
    return YES;
}

- (void)windowDidResize:(NSNotification *)notification {
    [self layoutSubviews];
}

// Esc / ⌘R / 顶部按钮：向子进程写入 ESC 行，Python 在任意输入点识别并回到主界面。
// ↑ / ↓：在当前屏的可选项之间移动选中项（同时兼容直接输入）。
- (void)monitorKeys {
    __weak AppDelegate *weakSelf = self;
    [NSEvent addLocalMonitorForEventsMatchingMask:NSEventMaskKeyDown handler:^NSEvent *(NSEvent *event) {
        if (event.keyCode == 53) {  // Esc
            [weakSelf goHome];
            return nil;
        }
        if (event.keyCode == 126) { // ↑
            return [weakSelf moveSelection:-1] ? nil : event;
        }
        if (event.keyCode == 125) { // ↓
            return [weakSelf moveSelection:1] ? nil : event;
        }
        return event;
    }];
}

// 方向键切换选中项：把该项要提交的值填入输入框并高亮它。
// 直接输入仍可用——一旦用户手动改动输入框内容，就取消方向键选中态。
// 返回值表示本次是否确实消费了方向键（有可选项才消费）。
- (BOOL)moveSelection:(NSInteger)delta {
    NSArray *opts = self.selectOptions;
    if (!opts || opts.count == 0) return NO;

    NSInteger n = (NSInteger)opts.count;
    NSInteger cur = self.selectedIndex;
    NSInteger next;
    if (cur < 0) {
        // 首次按方向键：向下从第一项开始，向上从最后一项开始
        next = (delta > 0) ? 0 : n - 1;
    } else {
        next = (cur + delta) % n;
        if (next < 0) next += n;
    }
    self.selectedIndex = next;
    NSString *value = opts[next][@"value"] ?: @"";
    self.settingSelectionProgrammatically = YES;
    [self.input setStringValue:value];
    self.settingSelectionProgrammatically = NO;
    [self render];  // 触发高亮重绘
    return YES;
}

// 用户一旦手动改动输入框，就取消方向键选中高亮——避免"高亮 A、实际提交 B"的错觉。
- (void)controlTextDidChange:(NSNotification *)obj {
    if (self.settingSelectionProgrammatically) return;
    if (self.selectedIndex >= 0) {
        self.selectedIndex = -1;
        [self render];
    }
}

- (void)goHome {
    [self.input setStringValue:@""];
    if (!self.task || !self.task.isRunning) {
        return;
    }
    NSData *data = [@"\x1b\n" dataUsingEncoding:NSUTF8StringEncoding];
    [[self.stdinPipe fileHandleForWriting] writeData:data];
}

- (BOOL)control:(NSControl *)control textView:(NSTextView *)textView
doCommandBySelector:(SEL)commandSelector {
    if (commandSelector == @selector(insertNewline:)) {
        [self submitInput];
        return YES;
    }
    return NO;
}

- (void)submitInput {
    // 空输入也是有效输入：主程序把空行解释为「选中当前活动网卡」，必须把换行发给子进程
    NSString *line = [self.input stringValue] ?: @"";
    [self.input setStringValue:@""];
    self.selectedIndex = -1;  // 提交后交回下一屏，避免旧高亮短暂残留
    // 输出区与输入框彼此独立，不要往 raw 插换行——那会让旧内容在清屏前闪一下
    if (!self.task || !self.task.isRunning) {
        return;
    }
    NSData *data = [[line stringByAppendingString:@"\n"] dataUsingEncoding:NSUTF8StringEncoding];
    [[self.stdinPipe fileHandleForWriting] writeData:data];
}

// ------------------------------- 输出渲染 -------------------------------
// Python 端输出结构化指令：每行以 \001TYPE\001 开头，后跟用 \002 分隔的字段。

- (void)appendPlain:(NSString *)text {
    if (!self.raw) {
        self.raw = [NSMutableString new];
    }
    [self.raw appendString:text];
    [self render];
}

- (void)appendData:(NSData *)data {
    NSString *text = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    if (!text) {
        text = [[NSString alloc] initWithData:data encoding:NSISOLatin1StringEncoding];
    }
    if (text.length) {
        [self appendPlain:text];
    }
}

static NSCharacterSet *SetIPFieldSep(void) {
    static NSCharacterSet *set = nil;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ set = [NSCharacterSet characterSetWithCharactersInString:@"\002"]; });
    return set;
}

- (NSArray *)fieldsOfLine:(NSString *)line type:(NSString **)typeOut {
    if (line.length < 2 || [line characterAtIndex:0] != 1) {
        if (typeOut) *typeOut = @"text";
        return @[line];
    }
    NSRange end = [line rangeOfString:@"\001" options:0 range:NSMakeRange(1, line.length - 1)];
    if (end.location == NSNotFound) {
        if (typeOut) *typeOut = @"text";
        return @[line];
    }
    NSString *type = [line substringWithRange:NSMakeRange(1, end.location - 1)];
    NSString *rest = [line substringFromIndex:NSMaxRange(end)];
    if (typeOut) *typeOut = type;
    return [rest componentsSeparatedByCharactersInSet:SetIPFieldSep()];
}

- (NSMutableParagraphStyle *)para:(CGFloat)before after:(CGFloat)after {
    NSMutableParagraphStyle *p = [NSMutableParagraphStyle new];
    p.lineBreakMode = NSLineBreakByWordWrapping;
    p.paragraphSpacingBefore = before;
    p.paragraphSpacing = after;
    p.minimumLineHeight = 25;
    return p;
}

- (NSAttributedString *)run:(NSString *)text
                       font:(NSFont *)font
                      color:(NSColor *)color
                      para:(NSParagraphStyle *)para {
    NSMutableDictionary *a = [NSMutableDictionary new];
    if (font) a[NSFontAttributeName] = font;
    if (color) a[NSForegroundColorAttributeName] = color;
    if (para) a[NSParagraphStyleAttributeName] = para;
    return [[NSAttributedString alloc] initWithString:(text ?: @"") attributes:a];
}

- (NSFont *)ui:(CGFloat)size weight:(NSFontWeight)weight {
    return [NSFont systemFontOfSize:size weight:weight];
}

- (NSFont *)mono:(CGFloat)size {
    NSFont *f = [NSFont fontWithName:@"SFMono-Regular" size:size];
    return f ?: [NSFont fontWithName:@"Menlo" size:size];
}

// 圆角徽章：段落背景色实现色块，左右空格做内边距
- (NSAttributedString *)badge:(NSString *)text
                         fore:(NSColor *)fore
                         back:(NSColor *)back
                         para:(NSParagraphStyle *)para {
    NSMutableDictionary *a = [NSMutableDictionary new];
    a[NSFontAttributeName] = [self ui:12.5 weight:NSFontWeightSemibold];
    a[NSForegroundColorAttributeName] = fore;
    a[NSBackgroundColorAttributeName] = back;
    a[NSParagraphStyleAttributeName] = para;
    return [[NSAttributedString alloc] initWithString:[NSString stringWithFormat:@" %@ ", text] attributes:a];
}

// 当前行是否是方向键选中项（按 token 首字段匹配）
- (BOOL)isSelectedKey:(NSString *)key {
    if (self.selectedIndex < 0 || self.selectedIndex >= (NSInteger)self.selectOptions.count) return NO;
    NSString *sel = self.selectOptions[self.selectedIndex][@"key"] ?: @"";
    return [sel isEqualToString:key];
}

// 给选中行加一个左侧箭头 + 淡色底，形成明确的"光标落在这一项"视觉
- (NSAttributedString *)markSelected:(NSMutableAttributedString *)r para:(NSParagraphStyle *)p {
    [r insertAttributedString:[self run:@"▸ " font:[self ui:14 weight:NSFontWeightSemibold]
                                   color:SetIPBlue() para:p] atIndex:0];
    [r addAttribute:NSBackgroundColorAttributeName value:SetIPHex(@"25324A")
             range:NSMakeRange(0, r.length)];
    return r;
}

- (NSAttributedString *)renderTypedLine:(NSString *)line {
    NSString *type = nil;
    NSArray *f = [self fieldsOfLine:line type:&type];
    NSString *(^val)(NSUInteger) = ^NSString *(NSUInteger i) {
        return i < f.count ? f[i] : @"";
    };
    NSParagraphStyle *p = [self para:3 after:3];

    if ([type isEqualToString:@"title"]) {
        return [self run:val(0) font:[self ui:16 weight:NSFontWeightSemibold]
                   color:SetIPBlue() para:[self para:18 after:10]];
    }
    if ([type isEqualToString:@"sub"]) {
        return [self run:val(0) font:[self ui:13 weight:NSFontWeightRegular]
                   color:SetIPGrey() para:[self para:0 after:8]];
    }
    if ([type isEqualToString:@"adapter"]) {
        NSMutableAttributedString *r = [NSMutableAttributedString new];
        NSString *name = val(1);
        BOOL active = [val(2) boolValue];
        [r appendAttributedString:[self badge:val(0)
                                         fore:active ? [NSColor whiteColor] : SetIPBlue()
                                         back:active ? SetIPGreen() : SetIPChipBlue()
                                         para:p]];
        [r appendAttributedString:[self run:@"   " font:[self ui:14 weight:NSFontWeightRegular] color:nil para:p]];
        [r appendAttributedString:[self run:name
                                       font:[self ui:14.5 weight:active ? NSFontWeightSemibold : NSFontWeightMedium]
                                      color:active ? SetIPGreen() : SetIPInk() para:p]];
        if (active) {
            [r appendAttributedString:[self run:@"    " font:[self ui:14 weight:NSFontWeightRegular] color:nil para:p]];
            [r appendAttributedString:[self badge:@"当前活动" fore:SetIPGreen() back:SetIPChipGreen() para:p]];
        }
        return [self isSelectedKey:val(0)] ? [self markSelected:r para:p] : r;
    }
    if ([type isEqualToString:@"kv"]) {
        NSMutableAttributedString *r = [NSMutableAttributedString new];
        NSString *label = val(0);
        NSColor *lc = [label isEqualToString:@"公司"] ? SetIPGreen() :
                      [label isEqualToString:@"家里"] ? SetIPTeal() : SetIPPurple();
        [r appendAttributedString:[self badge:label fore:lc back:SetIPChipGrey() para:p]];
        [r appendAttributedString:[self run:@"   " font:[self ui:14 weight:NSFontWeightRegular] color:nil para:p]];
        [r appendAttributedString:[self run:val(1) font:[self mono:12]
                                       color:SetIPSub() para:p]];
        return r;
    }
    if ([type isEqualToString:@"menu"]) {
        NSMutableAttributedString *r = [NSMutableAttributedString new];
        [r appendAttributedString:[self badge:val(0) fore:[NSColor whiteColor] back:SetIPHex(@"3B6FD6") para:p]];
        [r appendAttributedString:[self run:@"   " font:[self ui:14 weight:NSFontWeightRegular] color:nil para:p]];
        [r appendAttributedString:[self run:val(1) font:[self ui:14 weight:NSFontWeightMedium]
                                       color:SetIPInk() para:p]];
        return [self isSelectedKey:val(0)] ? [self markSelected:r para:p] : r;
    }
    if ([type isEqualToString:@"hint"]) {
        return [self run:val(0) font:[self ui:12.5 weight:NSFontWeightRegular]
                   color:SetIPGrey() para:[self para:10 after:2]];
    }
    if ([type isEqualToString:@"step"]) {
        NSMutableAttributedString *r = [NSMutableAttributedString new];
        [r appendAttributedString:[self run:@"▸  " font:[self ui:14 weight:NSFontWeightSemibold]
                                       color:SetIPBlue() para:[self para:8 after:2]]];
        [r appendAttributedString:[self run:val(0) font:[self ui:14 weight:NSFontWeightMedium]
                                       color:SetIPInk() para:[self para:0 after:2]]];
        return r;
    }
    if ([type isEqualToString:@"ok"]) {
        NSMutableAttributedString *r = [NSMutableAttributedString new];
        [r appendAttributedString:[self badge:@"已生效" fore:SetIPGreen() back:SetIPChipGreen() para:p]];
        [r appendAttributedString:[self run:@"   " font:[self ui:14 weight:NSFontWeightRegular] color:nil para:p]];
        [r appendAttributedString:[self run:val(0) font:[self mono:12.5]
                                       color:SetIPSub() para:p]];
        return r;
    }
    if ([type isEqualToString:@"fail"]) {
        NSMutableAttributedString *r = [NSMutableAttributedString new];
        [r appendAttributedString:[self badge:@"未生效" fore:SetIPRed() back:SetIPChipRed() para:p]];
        [r appendAttributedString:[self run:@"   " font:[self ui:14 weight:NSFontWeightRegular] color:nil para:p]];
        [r appendAttributedString:[self run:val(0) font:[self ui:13 weight:NSFontWeightRegular]
                                       color:SetIPRed() para:p]];
        return r;
    }
    if ([type isEqualToString:@"warn"]) {
        return [self run:[NSString stringWithFormat:@"⚠  %@", val(0)]
                    font:[self ui:13 weight:NSFontWeightRegular] color:SetIPAmber()
                    para:[self para:6 after:2]];
    }
    if ([type isEqualToString:@"state"]) {
        NSMutableAttributedString *r = [NSMutableAttributedString new];
        [r appendAttributedString:[self run:val(0) font:[self ui:14 weight:NSFontWeightMedium]
                                       color:SetIPGrey() para:[self para:8 after:2]]];
        [r appendAttributedString:[self run:@"  " font:[self ui:14 weight:NSFontWeightRegular] color:nil para:[self para:0 after:2]]];
        [r appendAttributedString:[self run:val(1) font:[self mono:13]
                                       color:SetIPInk() para:[self para:0 after:2]]];
        return r;
    }
    if ([type isEqualToString:@"blank"]) {
        return [self run:@" " font:[self ui:8 weight:NSFontWeightRegular] color:nil para:[self para:0 after:0]];
    }
    // text / 未知：剥掉残留 ANSI 码，等宽兼容渲染
    NSString *plain = line;
    NSRegularExpression *sgr = [NSRegularExpression regularExpressionWithPattern:@"\033\\[[0-9;]*m"
                                                                         options:0 error:nil];
    plain = [sgr stringByReplacingMatchesInString:plain options:0
                                           range:NSMakeRange(0, plain.length) withTemplate:@""];
    return [self run:plain font:[self mono:13] color:SetIPSub() para:[self para:3 after:3]];
}

// 把一段（分区）的多行渲染成富文本；withTitle=YES 时首行作为栏目标题突出显示
- (NSAttributedString *)renderSection:(NSArray *)lines title:(NSString *)title {
    NSMutableAttributedString *r = [NSMutableAttributedString new];
    if (title.length) {
        [r appendAttributedString:[self run:title font:[self ui:14.5 weight:NSFontWeightSemibold]
                                        color:SetIPBlue() para:[self para:0 after:8]]];
        [r appendAttributedString:[self run:@"\n" font:[self ui:6 weight:NSFontWeightRegular]
                                       color:nil para:nil]];
    }
    for (NSString *line in lines) {
        if (line.length == 0) continue;
        [r appendAttributedString:[self renderTypedLine:line]];
        [r appendAttributedString:[self run:@"\n" font:[self ui:6 weight:NSFontWeightRegular]
                                        color:nil para:nil]];
    }
    return r;
}

// 把一组 token 行渲染进固定槽位（紧凑行距；空列表显示淡色占位，避免大片空白）
- (void)drawLines:(NSArray<NSString *> *)lines into:(SetIPCanvas *)view placeholder:(NSString *)placeholder {
    NSMutableAttributedString *r = [NSMutableAttributedString new];
    self.compactRendering = YES;
    if (lines.count == 0 && placeholder.length) {
        [r appendAttributedString:[self run:placeholder font:[self ui:13 weight:NSFontWeightRegular]
                                        color:SetIPHex(@"5E6472") para:[self para:0 after:0]]];
    }
    for (NSString *line in lines) {
        if (line.length == 0) continue;
        [r appendAttributedString:[self renderTypedLine:line]];
        [r appendAttributedString:[self run:@"\n" font:[self ui:6 weight:NSFontWeightRegular]
                                        color:nil para:nil]];
    }
    self.compactRendering = NO;
    [view setContent:r];
}

- (void)render {
    // 遇到 ANSI 清屏（ESC[2J / ESC[H）时，只解析最后一次清屏之后的内容
    NSString *source = self.raw ?: @"";
    NSRange clear2J = [source rangeOfString:@"\033[2J" options:NSBackwardsSearch];
    NSRange clearH  = [source rangeOfString:@"\033[H"  options:NSBackwardsSearch];
    NSUInteger from = 0;
    if (clear2J.location != NSNotFound) from = MAX(from, NSMaxRange(clear2J));
    if (clearH.location  != NSNotFound) from = MAX(from, NSMaxRange(clearH));
    NSString *visible = from > 0 ? [source substringFromIndex:from] : source;

    // 换屏时重置方向键选中态
    if (from > self.lastClearFrom) {
        self.lastClearFrom = from;
        self.selectedIndex = -1;
    }

    // 按类型把当前屏的 token 分到四个固定槽位。title 忽略（槽位标题已固定）。
    NSMutableArray *adapterLines = [NSMutableArray array];
    NSMutableArray *stateLines   = [NSMutableArray array];
    NSMutableArray *kvLines      = [NSMutableArray array];
    NSMutableArray *actionLines  = [NSMutableArray array];
    NSMutableArray *footerLines  = [NSMutableArray array];
    NSMutableArray *options      = [NSMutableArray array]; // 方向键可选项，仅取当前屏

    for (NSString *line in [visible componentsSeparatedByString:@"\n"]) {
        if (line.length == 0) continue;
        NSString *type = nil;
        [self fieldsOfLine:line type:&type];
        NSArray *f = [self fieldsOfLine:line type:nil];
        NSString *v0 = f.count ? f[0] : @"";

        if ([type isEqualToString:@"hint"] || [type isEqualToString:@"sub"]) {
            [footerLines addObject:v0];
            continue;
        }
        if ([type isEqualToString:@"title"]) continue;

        // adapter 首字段形如 [0]：提交给 Python 时去掉方括号；menu 的 1/2/3/4 直接可用
        if ([type isEqualToString:@"adapter"] || [type isEqualToString:@"menu"]) {
            NSString *value = v0;
            if ([type isEqualToString:@"adapter"]) {
                value = [value stringByTrimmingCharactersInSet:
                         [NSCharacterSet characterSetWithCharactersInString:@"[]"]];
            }
            [options addObject:@{@"key": v0, @"value": value, @"line": line}];
        }
        if ([type isEqualToString:@"adapter"]) { [adapterLines addObject:line]; continue; }
        if ([type isEqualToString:@"state"])   { [stateLines addObject:line];   continue; }
        if ([type isEqualToString:@"kv"])      { [kvLines addObject:line];      continue; }
        [actionLines addObject:line]; // menu / step / ok / fail / warn / text
    }

    self.selectOptions = options;
    if (self.selectedIndex >= (NSInteger)options.count) self.selectedIndex = -1;

    // 信息面板：本屏出现该类内容才刷新缓存，否则沿用上一屏——这就是"界面不跳动"的关键。
    if (adapterLines.count) self.cachedNet = adapterLines;
    if (stateLines.count)   self.cachedStatus = stateLines;
    if (kvLines.count)      self.cachedConfig = kvLines;
    if (actionLines.count)  self.cachedAction = actionLines;

    [self drawLines:self.cachedNet    into:self.netView    placeholder:@"选择一张网卡，或用 ↑↓ 方向键切换"];
    [self drawLines:self.cachedStatus into:self.statusView placeholder:@"选中网卡后显示实时状态"];
    [self drawLines:self.cachedConfig into:self.configView placeholder:@"当前配置"];
    [self drawLines:self.cachedAction into:self.actionView placeholder:@"选择网卡后显示可用操作"];

    // 底部提示条：高度固定，内容只在本屏有提示时更新
    if (footerLines.count) {
        NSMutableAttributedString *fh = [NSMutableAttributedString new];
        for (NSUInteger i = 0; i < footerLines.count; i++) {
            if (i) [fh appendAttributedString:[self run:@"   ·   " font:[self ui:12 weight:NSFontWeightRegular]
                                                   color:SetIPGrey() para:nil]];
            [fh appendAttributedString:[self run:footerLines[i] font:[self ui:12.5 weight:NSFontWeightRegular]
                                                   color:SetIPGrey() para:[self para:2 after:2]]];
        }
        [[self.hintBar textStorage] setAttributedString:fh];
        [self.hintBar setHidden:NO];
        self.hintHeight = 28;
    } else {
        [self.hintBar setHidden:NO]; // 始终占位，避免高度变化挤动槽位
        [[self.hintBar textStorage] setAttributedString:[NSMutableAttributedString new]];
        self.hintHeight = 28;
    }

    [self layoutSubviews];
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        AppDelegate *delegate = [AppDelegate new];
        [app setDelegate:delegate];
        [app run];
    }
    return 0;
}
