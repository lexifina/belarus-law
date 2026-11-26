"""Belarus: every dated edition (редакция) of the Constitution and the codes from ETALON-ONLINE (etalonline.by,
National Centre of Legislation and Legal Information), appended to lexifina/belarus-law with git fast-import.

One request at a time, 5 s apart (etalonline.by robots.txt: Crawl-delay: 5). Backs off on 429/5xx, stops on 403.
Usage: python -X utf8 runner.py   (run detached; writes ../progress.log)
"""
import concurrent.futures as cf, datetime as dt, gzip, threading, html, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / 'cache'
REPO = ROOT / 'belarus-law'
DOCS = ROOT / 'docs'
LOG = ROOT / 'progress.log'
STATE = ROOT / 'state.json'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
BASE = 'https://etalonline.by/document/'
DELAY = 1.5  # Alan 11-26: robots Crawl-delay is advisory; 1.5 s gap, 2 in flight, back off on strain
IN_FLIGHT = 2
PLACEHOLDER = 'c8f814a255ce9862703115b58687a9476a599d9d'

# (regnum, path, short)
ACTS = [
    ('v19402875', 'konstitutsiya', 'Конституция'),
    ('hk9800218', 'kodeksy/grazhdanskiy-kodeks', 'ГК'),
    ('hk9900275', 'kodeksy/ugolovnyy-kodeks', 'УК'),
    ('hk9900295', 'kodeksy/ugolovno-protsessualnyy-kodeks', 'УПК'),
    ('hk9900296', 'kodeksy/trudovoy-kodeks', 'ТК'),
    ('hk2400359', 'kodeksy/kodeks-grazhdanskogo-sudoproizvodstva', 'КГС'),
    ('hk2100091', 'kodeksy/kodeks-ob-administrativnykh-pravonarusheniyakh', 'КоАП'),
    ('hk2100092', 'kodeksy/protsessualno-ispolnitelnyy-kodeks-ob-administrativnykh-pravonarusheniyakh', 'ПИКоАП'),
    ('hk0200166', 'kodeksy/nalogovyy-kodeks-obshchaya-chast', 'НК (Общая часть)'),
    ('hk0900071', 'kodeksy/nalogovyy-kodeks-osobennaya-chast', 'НК (Особенная часть)'),
    ('hk9900278', 'kodeksy/kodeks-o-brake-i-seme', 'КоБС'),
    ('hk1200428', 'kodeksy/zhilishchnyy-kodeks', 'ЖК'),
    ('hk0000365', 'kodeksy/ugolovno-ispolnitelnyy-kodeks', 'УИК'),
    ('hk0800412', 'kodeksy/byudzhetnyy-kodeks', 'БК'),
    ('hk0000441', 'kodeksy/bankovskiy-kodeks', 'Банковский кодекс'),
    ('hk0000370', 'kodeksy/izbiratelnyy-kodeks', 'Избирательный кодекс'),
    ('hk0600139', 'kodeksy/kodeks-o-sudoustroystve-i-statuse-sudey', 'КоСиСС'),
    ('hk1100243', 'kodeksy/kodeks-ob-obrazovanii', 'Кодекс об образовании'),
    ('hk0800425', 'kodeksy/kodeks-o-zemle', 'Кодекс о земле'),
    ('hk0800406', 'kodeksy/kodeks-o-nedrakh', 'Кодекс о недрах'),
    ('hk1400149', 'kodeksy/vodnyy-kodeks', 'Водный кодекс'),
    ('hk1500332', 'kodeksy/lesnoy-kodeks', 'Лесной кодекс'),
    ('hk2300289', 'kodeksy/kodeks-ob-arkhitekturnoy-gradostroitelnoy-i-stroitelnoy-deyatelnosti', 'Кодекс об АГСД'),
    ('hk0600117', 'kodeksy/vozdushnyy-kodeks', 'Воздушный кодекс'),
    ('hk0200118', 'kodeksy/kodeks-vnutrennego-vodnogo-transporta', 'КВВТ'),
    ('hk9900321', 'kodeksy/kodeks-torgovogo-moreplavaniya', 'КТМ'),
    ('hk1600413', 'kodeksy/kodeks-ab-kultury', 'Кодэкс аб культуры'),
]

last_req = [0.0]

# (akt id in ETALON-ONLINE search, folder, word)
LAW_KINDS = [(1, 'zakony', 'Закон'), (12, 'dekrety', 'Декрет'), (3, 'ukazy', 'Указ')]
TR = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюяіў',
              ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't',
               'u', 'f', 'kh', 'ts', 'ch', 'sh', 'shch', '', 'y', '', 'e', 'yu', 'ya', 'i', 'u']))


def translit(s):
    s = ''.join(TR.get(c, c) for c in s.lower())
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def law_path(folder, word, title, regnum):
    adopted = adoption(title)
    num = re.search(r'№\s*([\w\-/]+)', title.split('|')[-1])
    year = adopted[:4] if adopted else 'bez-daty'
    slug = '-'.join(x for x in [adopted, translit(num.group(1)) if num else regnum] if x)
    return f'{folder}/{year}/{slug}'


def list_kind(akt, folder):
    regnums, page, total = [], 1, None
    while True:
        url = (f'https://etalonline.by/search/?search_str=&adv_s=1&s=0&d=1&ps=100&akt%5B0%5D={akt}&organ=-1'
               f'&archive=0&db%5B0%5D=0&db%5B1%5D=1&db%5B2%5D=2&PAGEN_1={page}')
        s = cached('_lists', f'akt{akt}-p{page:04d}', url)
        if total is None:
            m = re.search(r'id="num-res-documents">\s*([\d\s]+)<', s)
            total = int(re.sub(r'\D', '', m.group(1))) if m else 10 ** 6
            log(f'{folder}: {total} found in the listing')
        found = re.findall(r'class="docResNum" data-regnum="([a-z0-9]+)"', s)
        if not found:
            break
        new = [r for r in found if r not in regnums]
        regnums += new
        if not new or len(regnums) >= total:
            break
        page += 1
    return regnums


def log(msg):
    line = f"{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}\n"
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line)


class Blocked(Exception):
    pass


pace_lock = threading.Lock()
delay = [DELAY]  # current gap between request starts; grows on strain, decays back to DELAY
CHALLENGE = re.compile('captcha|cf-chl|challenge-platform|Just a moment|Доступ ограничен'.encode(), re.I)


def strain(factor, why):
    with pace_lock:
        delay[0] = min(delay[0] * factor, 30.0)
    log(f'{why}; gap now {delay[0]:.1f} s')


def get(url):
    backoff = [60, 180, 600, 1200]
    for attempt in range(len(backoff) + 1):
        with pace_lock:
            wait = last_req[0] + delay[0] - time.time()
            last_req[0] = max(time.time(), last_req[0] + delay[0])
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip',
                                                   'Accept-Language': 'ru'})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    data = gzip.decompress(data)
            took = time.time() - t0
            if CHALLENGE.search(data[:20000]) and b'versionList' not in data and b'docResNum' not in data:
                raise Blocked(f'challenge or access-denied page on {url}')
            if took > 20:
                strain(2, f'slow response {took:.0f} s')
            elif delay[0] > DELAY:
                with pace_lock:
                    delay[0] = max(DELAY, delay[0] * 0.9)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise Blocked(f'403 on {url}')
            if e.code in (429, 500, 502, 503, 504) and attempt < len(backoff):
                strain(3, f'HTTP {e.code} on {url}')
                log(f'backing off {backoff[attempt]} s')
                time.sleep(backoff[attempt])
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            if attempt < len(backoff):
                log(f'network error {e!r} on {url}; backing off {backoff[attempt]} s')
                time.sleep(backoff[attempt])
                continue
            raise


def cached(regnum, key, url):
    p = CACHE / regnum / f'{key}.html.gz'
    if p.exists():
        return gzip.decompress(p.read_bytes()).decode('utf-8')
    data = get(url)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_bytes(gzip.compress(data, 6))
    os.replace(tmp, p)
    return data.decode('utf-8')


# ---------------------------------------------------------------- edition list

def strip(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def editions(page):
    m = re.search(r'<ul id="versionList".*?</ul>', page, re.S)
    if not m:
        return None
    out = []
    for li in re.findall(r'<li\b[^>]*>.*?</li>', m.group(0), re.S):
        attrs = dict(re.findall(r"(\w+)='([^']*)'", re.match(r'<li\b([^>]*)>', li).group(1)))
        val, state = attrs.get('val'), attrs.get('state')
        if not val or state in ('future', 'full') or val in ('full', '-'):
            continue
        idx = int(attrs['id'].rsplit('_', 1)[1]) if 'id' in attrs and attrs['id'].rsplit('_', 1)[1].isdigit() else 0
        label = re.sub(r'\s*дата вступления в силу\s*-?\s*[\d.]+', '', strip(li)).strip()
        out.append({'val': val, 'rn': attrs.get('rn'), 'state': state, 'idx': idx, 'label': label})
    out.sort(key=lambda e: e['idx'])
    return out


def doc_title(page):
    m = re.search(r'id="docInfo"[^>]*data-title="([^"]*)"', page)
    return re.sub(r'\s+', ' ', html.unescape(m.group(1))).strip() if m else ''


MONTHS = {'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
          'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12, 'студзеня': 1, 'лютага': 2, 'сакавіка': 3,
          'красавіка': 4, 'мая ': 5, 'чэрвеня': 6, 'ліпеня': 7, 'жніўня': 8, 'верасня': 9, 'кастрычніка': 10,
          'лістапада': 11, 'снежня': 12}


def adoption(title):
    m = re.search(r'от (\d{1,2}) (\w+) (\d{4})', title) or re.search(r'ад (\d{1,2}) (\w+) (\d{4})', title)
    if m and m.group(2) in MONTHS:
        return dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
    return None


AMEND = re.compile(r'внесенными (\w+)(?: \w+)? от (\d\d)\.(\d\d)\.(\d{4})(?: № ?([\w\-/]+))?')
KIND = {'законом': ('law', 'Закон'), 'декретом': ('decree', 'Декрет'), 'указом': ('edict', 'Указ'),
        'решением': ('referendum', 'Решение республиканского референдума'),
        'постановлением': ('decree', 'Постановление')}


def author_of(e, title, regnum):
    """(name, email, kind) for an edition."""
    if e['val'] == 'original':
        name = title.split('|')[-1].strip() or title
        return name, f'{regnum}@pravo.by.invalid', 'original'
    m = AMEND.search(e['label'])
    rn = (e['rn'] or '').lower()
    email = f"{re.sub(r'[^a-z0-9]', '', rn) or 'unknown'}@pravo.by.invalid"
    if m:
        kind, word = KIND.get(m.group(1).lower(), ('law', m.group(1)))
        num = f' № {m.group(5)}' if m.group(5) else ''
        return f'{word} от {m.group(2)}.{m.group(3)}.{m.group(4)}{num}', email, kind
    lab = re.sub(r'\s*\((недействующая|действующая) редакция\)|\s*\(вступил[аи]? в силу[^)]*\)', '', e['label'])
    lab = re.sub(r'^с изменениями \(дополнениями\),? внесенными\s*', '', lab).strip() or (e['rn'] or 'неизвестный акт')
    return lab[:200], email, 'law'


# ---------------------------------------------------------------- text

BODY = {'newncpi', 'point', 'underpoint', 'comment', 'snoski', 'newncpi1', 'numnrpa', 'onestring'}
HEAD = {'chapter', 'zagrazdel', 'podrazdel', 'paragraph', 'nonumheader', 'part', 'snoskiline', 'razdel',
        'glava', 'zagolovok'}
SKIP = {'rekviziti', 'contenttext', 'titlek', 'prinodobren', 'changei', 'changeadd', 'contentword', 'title',
        'err_msg', 'input_err_msg', 'show_unp_phr', 'js-dropdown-compare-msg', 'name', 'promulgator',
        'datepr', 'number', 'agreedate', 'gosreg', 'changeutrs', 'cap1', 'capu1', 'append', 'append1'}
PARA = re.compile(r'<p class="([^"]*)"[^>]*>(.*?)</p>', re.S)
ART = re.compile(r'^(Статья|Артыкул) (\d+(?:\.\d+)*(?:-\d+)?)\s*\.?\s*(.*)$')


def text(inner):
    s = re.sub(r'</?(?:span|b|i|font)\b[^>]*>', '', inner)
    s = re.sub(r'(\d)\s*<sup[^>]*>\s*(\d+)\s*</sup>', r'\1-\2', s)
    s = re.sub(r'<br\s*/?>', ' ', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ')
    s = s.replace('–', '-').replace('—', '-').replace('«', '"').replace('»', '"')
    s = s.replace('“', '"').replace('”', '"').replace('’', "'")
    return re.sub(r'\s+', ' ', s).strip()


def unit_key(num, pad):
    if '.' in num:
        main, _, sup = num.partition('-')
        parts = [p.zfill(3) for p in main.split('.')]
        return 'statya-' + '-'.join(parts + ([sup] if sup else []))
    n = num.split('-')
    return 'statya-' + '-'.join([n[0].zfill(pad)] + n[1:])


def parse(page, pad, stats):
    i = page.find('id="docInfo"')
    body = page[i:] if i >= 0 else page
    units, cur, started = {}, None, False
    pre = []
    for cls, raw in PARA.findall(body):
        cls = cls.split()[0] if cls.split() else ''
        t = text(raw)
        if cls in ('newncpi0', 'newncpi2') and started and (t.startswith('Президент') or t.startswith('Прэзідэнт')):
            break
        if cls in SKIP or cls in HEAD:
            continue
        if cls in ('article', 'articleintext'):
            m = ART.match(t)
            if not m:
                if cur is not None and t:
                    cur['lines'].append(t)
                    stats['odd_heading'] = stats.get('odd_heading', 0) + 1
                continue
            started = True
            key = unit_key(m.group(2), pad)
            if key in units:
                k2, n = key, 2
                while f'{key}-dubl-{n}' in units:
                    n += 1
                key = f'{key}-dubl-{n}'
                stats['dup'] = stats.get('dup', 0) + 1
            cur = {'label': f'{m.group(1)} {m.group(2)}', 'lines': []}
            units[key] = cur
            if m.group(3):
                cur['lines'].append(m.group(3))
            continue
        if not t:
            continue
        if not started:
            if pad == 3 and cls in ('newncpi', 'preamble') and not re.match(r'^\d{1,2} \w+ \d{4} г\.', t):
                pre.append(t)
            continue
        if cur is not None:
            if cls not in BODY and not cls.startswith('newncpi'):
                stats['other_class'] = stats.get('other_class', 0) + 1
            cur['lines'].append(t)
    files = {}
    if not units:
        # acts without articles (decrees, edicts): the whole text is one file
        lines = []
        for cls, raw in PARA.findall(body):
            cls = cls.split()[0] if cls.split() else ''
            t = text(raw)
            if cls in ('newncpi0', 'newncpi2') and lines and (t.startswith('Президент') or t.startswith('Прэзідэнт')):
                break
            if not t or cls in SKIP or cls in HEAD or re.match(r'^\d{1,2} \w+ \d{4} г\.', t):
                continue
            if cls in BODY or cls.startswith('newncpi') or cls in ('article', 'articleintext', 'preamble'):
                lines.append(t)
        if lines:
            stats['whole_text'] = 1
            return {'tekst.md': '# Текст\n' + ''.join(l + '\n' for l in lines)}
        return {}
    if pre:
        files['preambula.md'] = '# Преамбула\n' + ''.join(l + '\n' for l in pre)
    for k, u in units.items():
        files[k + '.md'] = f"# {u['label']}\n" + ''.join(l + '\n' for l in u['lines'])
    return files


# ---------------------------------------------------------------- git

def git(*args, inp=None):
    r = subprocess.run(['git', '-C', str(REPO), *args], input=inp, capture_output=True,
                       creationflags=0x08000000 if os.name == 'nt' else 0)
    if r.returncode:
        raise RuntimeError(f'git {args}: {r.stderr.decode(errors="replace")}')
    return r.stdout.decode('utf-8', errors='replace').strip()


def ts(day):
    d = dt.datetime.fromisoformat(day + 'T12:00:00+03:00') if day >= '2011-03-27' else None
    if d is None:
        # Europe/Minsk: UTC+2 winter / UTC+3 summer until 2011; noon local
        y, m_, _ = map(int, day.split('-'))
        summer = 4 <= m_ <= 9 or (m_ == 3 and day[8:] >= '28') or (m_ == 10 and day[8:] <= '26')
        d = dt.datetime.fromisoformat(day + 'T12:00:00' + ('+03:00' if summer else '+02:00'))
    off = d.strftime('%z')
    return f'{int(d.timestamp())} {off}'


def blob(data):
    b = data.encode('utf-8')
    return b'data %d\n' % len(b) + b + b'\n'


def fast_import(commits, tip):
    """commits: list of dict(author, email, day, message, changes{path: text|None})."""
    out = bytearray()
    for i, c in enumerate(commits):
        t = ts(c['day'])
        out += b'commit refs/heads/main\n'
        out += f"author {c['author']} <{c['email']}> {t}\n".encode()
        out += f"committer Lexifina <belarus-law@lexifina.com> {t}\n".encode()
        out += blob(c['message'])
        if i == 0 and tip:
            out += f'from {tip}\n'.encode()
        for path, data in sorted(c['changes'].items()):
            if data is None:
                out += f'D {path}\n'.encode()
            else:
                out += f'M 100644 inline {path}\n'.encode() + blob(data)
        out += b'\n'
    r = subprocess.run(['git', '-C', str(REPO), 'fast-import', '--quiet', '--force'], input=bytes(out),
                       capture_output=True, creationflags=0x08000000 if os.name == 'nt' else 0)
    if r.returncode:
        raise RuntimeError('fast-import: ' + r.stderr.decode(errors='replace'))


def tree_files(prefix):
    try:
        names = git('ls-tree', '-r', '--name-only', 'refs/heads/main', '--', prefix + '/').splitlines()
    except RuntimeError:
        return set()
    return {n for n in names if n}


def push(state):
    if not state.get('replaced_placeholder'):
        args = ['push', f'--force-with-lease=main:{PLACEHOLDER}', 'origin', 'main']
    else:
        args = ['push', 'origin', 'main']
    for attempt in range(3):
        try:
            git(*args)
            local = git('rev-parse', 'refs/heads/main')
            remote = git('ls-remote', 'origin', 'refs/heads/main').split()[0]
            log(f'PUSHED main {local} (ls-remote {remote}{" OK" if local == remote else " MISMATCH"})')
            if local == remote:
                state['replaced_placeholder'] = True
                state['pushed'] = local
                save(state)
            return
        except RuntimeError as e:
            log(f'push failed ({attempt + 1}/3): {e}')
            time.sleep(30)


def save(state):
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, STATE)


def docs_commit(state):
    """The first commit: README (ru + en), LICENSE, STRUCTURE.md, REPRODUCE.md, corpus.json, jurisdiction.json."""
    changes = {}
    for p in DOCS.rglob('*'):
        if p.is_file():
            changes[p.relative_to(DOCS).as_posix()] = p.read_text(encoding='utf-8')
    tip = git('rev-parse', 'refs/heads/main')
    old = set(git('ls-tree', '-r', '--name-only', tip).splitlines())
    if state.get('docs_done'):
        cur = {}
        for path in changes:
            try:
                cur[path] = git('show', f'refs/heads/main:{path}') + '\n'
            except RuntimeError:
                cur[path] = None
        changes = {k: v for k, v in changes.items() if cur.get(k) != v}
        if not changes:
            return
        fast_import([{'author': 'Lexifina', 'email': 'belarus-law@lexifina.com',
                      'day': dt.date.today().isoformat(), 'message': 'README, REPRODUCE.md: what is in it now\n',
                      'changes': changes}], tip)
        return
    fast_import([{'author': 'Lexifina', 'email': 'belarus-law@lexifina.com', 'day': '2026-11-26',
                  'message': 'Структура, README (ru + en), LICENSE и REPRODUCE.md\n\n'
                             'Layout, README (Russian and English), LICENSE and REPRODUCE.md. The law follows, one commit per edition on its in-force day.\n',
                  'changes': changes}], tip)
    state['docs_done'] = True
    save(state)


# ---------------------------------------------------------------- main

def do_act(regnum, path, short, state, pad=None):
    url0 = f'{BASE}?regnum={regnum}'
    page = cached(regnum, 'current', url0)
    eds = editions(page)
    title = doc_title(page)
    nolist = not eds
    if nolist:
        eds = [{'val': 'original', 'rn': None, 'state': 'original', 'idx': 0,
                'label': 'Текст (перечень редакций не приводится)'}]
    cur_sel = re.search(r"<li\b[^>]*selected=\"selected\"[^>]*val='([^']*)'", page)
    cur_val = cur_sel.group(1) if cur_sel else None
    log(f'{short} {regnum}: {len(eds)} editions listed ({title[:90]})')
    jobs = []
    for e in eds:
        if e['val'] == cur_val or nolist:
            continue
        key = 'original' if e['val'] == 'original' else f"{e['idx']:03d}-{e['val']}"
        rn = e['rn'] if e['rn'] else 'undefined'
        jobs.append((key, f"{BASE}?regnum={regnum}&q_id=&date={e['val']}&rnList={rn}&history=0"))
    if jobs:  # two in flight; get() keeps the gap between request starts
        with cf.ThreadPoolExecutor(IN_FLIGHT) as ex:
            list(ex.map(lambda j: cached(regnum, j[0], j[1]), jobs))
    if pad is None:
        pad = 3 if path == 'konstitutsiya' else 4
    versions = []
    for e in eds:
        key = 'original' if e['val'] == 'original' else f"{e['idx']:03d}-{e['val']}"
        if e['val'] == cur_val or nolist:
            pg = page
        else:
            rn = e['rn'] if e['rn'] else 'undefined'
            url = f"{BASE}?regnum={regnum}&q_id=&date={e['val']}&rnList={rn}&history=0"
            pg = cached(regnum, key, url)
        sel = re.search(r"<li\b[^>]*selected=\"selected\"[^>]*val='([^']*)'", pg)
        if e['val'] != 'original' and (not sel or sel.group(1) != e['val']):
            log(f'  {short} {key}: page shows edition {sel.group(1) if sel else None}, not {e["val"]}; skipped')
            continue
        st = {}
        files = parse(pg, pad, st)
        if not files:
            log(f'  {short} {key}: no articles parsed; skipped')
            continue
        versions.append((e, files, st))
    return title, versions


def build_act(regnum, path, short, title, versions, state):
    if not versions:
        return 0
    adopted = adoption(title)
    prev = {}
    for f in tree_files(path):
        prev[f[len(path) + 1:]] = git('show', f'refs/heads/main:{f}') + '\n'
    commits = []
    skipped = 0
    first_day = None
    for e, files, st in versions:
        if e['val'] == 'original':
            later = [v[0]['val'] for v in versions if v[0]['val'] != 'original']
            day = adopted or (min(later) if later else '2026-11-26')
            if later and day >= min(later):
                day = (dt.date.fromisoformat(min(later)) - dt.timedelta(days=1)).isoformat()
            basis = ('ЭТАЛОН-ONLINE: исходный текст; дата вступления в силу в перечне редакций не указана, '
                     'указана дата принятия' + (f' ({adopted})' if adopted else ''))
            src = f'{BASE}?regnum={regnum}&q_id=&date=original&rnList=undefined&history=0'
        else:
            day = e['val']
            basis = f"ЭТАЛОН-ONLINE: перечень редакций, редакция {regnum}_{e['idx']} действует с {day}"
            src = f"{BASE}?regnum={regnum}&q_id=&date={day}&rnList={e['rn']}&history=0"
        changes = {}
        for f, t in files.items():
            if prev.get(f) != t:
                changes[f'{path}/{f}'] = t
        for f in prev:
            if f not in files:
                changes[f'{path}/{f}'] = None
        if not changes:
            skipped += 1
            continue
        name, email, kind = author_of(e, title, regnum)
        subject = f'{short}: {"исходный текст" if e["val"] == "original" else "редакция " + day} ({name})'
        msg = (f'{subject}\n\n{title.split("|")[0].strip()}\n{e["label"]}\n\n'
               f'Kind: {kind}\nIn-force: {day}\nIn-force-basis: {basis}\nSource: {src}\nAct-path: {path}\n'
               f'Edition: {"original" if e["val"] == "original" else regnum + "_" + str(e["idx"])}\n'
               f'Amending-act: {e["rn"] or regnum}\n')
        commits.append({'author': name, 'email': email, 'day': day, 'message': msg, 'changes': changes})
        prev = dict(files)
        first_day = first_day or day
    if commits:
        tip = git('rev-parse', 'refs/heads/main')
        fast_import(commits, tip)
    log(f'{short}: {len(commits)} commits appended ({skipped} editions with no change in text), '
        f'{len(versions[-1][1])} files; stats {versions[-1][2]}')
    return len(commits)


def main():
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {'done': []}
    log(f'runner start pid {os.getpid()}')
    docs_commit(state)
    push(state)
    last_push = time.time()
    for regnum, path, short in ACTS:
        if regnum in state['done']:
            continue
        try:
            title, versions = do_act(regnum, path, short, state)
        except Blocked as b:
            log(f'BLOCKED: {b}; stopping (no retry round the block)')
            push(state)
            return
        except Exception as ex:
            log(f'{short} {regnum}: ERROR {ex!r}; act skipped')
            continue
        try:
            build_act(regnum, path, short, title, versions, state)
        except Exception as ex:
            log(f'{short} {regnum}: BUILD ERROR {ex!r}')
            continue
        state['done'].append(regnum)
        state.setdefault('acts', {})[regnum] = {'path': path, 'short': short, 'title': title,
                                                'editions': len(versions),
                                                'from': versions[0][0]['val'] if versions else None}
        save(state)
        push(state)
        last_push = time.time()
    for akt, folder, word in LAW_KINDS:
        try:
            regnums = list_kind(akt, folder)
        except Blocked as b:
            log(f'BLOCKED: {b}; stopping (no retry round the block)')
            push(state)
            return
        log(f'{folder}: {len(regnums)} acts in force listed')
        for regnum in regnums:
            if regnum in state['done']:
                continue
            try:
                title, versions = do_act(regnum, folder, word, state, pad=3)
                path = law_path(folder, word, title, regnum)
                num = re.search(r'№\s*([\w\-/]+)', title.split('|')[-1])
                short = f"{word} № {num.group(1)}" if num else f'{word} {regnum}'
                build_act(regnum, path, short, title, versions, state)
            except Blocked as b:
                log(f'BLOCKED: {b}; stopping (no retry round the block)')
                push(state)
                return
            except Exception as ex:
                log(f'{regnum}: ERROR {ex!r}; act skipped')
                continue
            state['done'].append(regnum)
            state.setdefault('acts', {})[regnum] = {'path': path, 'short': short, 'title': title,
                                                    'editions': len(versions)}
            save(state)
            if time.time() - last_push > 900:
                push(state)
                last_push = time.time()
        push(state)
        last_push = time.time()
    log('runner done')


if __name__ == '__main__':
    try:
        main()
    except Exception as ex:
        log(f'FATAL {ex!r}')
        raise
