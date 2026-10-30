"""Reconcile derived chat summaries against individual stream cards.

Only historical estimates are available: this does not classify raw chat.
Run with --write to update index.html, or without arguments to check it.
"""
import argparse
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
import re

from dashboard_html import groups, cards

ROOT = Path(__file__).resolve().parents[1]
LABELS = ['Позитив', 'Нейтраль', 'Негатив']
COLORS = ['pos', 'neu', 'neg']


def number(text):
    return int(re.sub(r'\D', '', text))


def fmt(value):
    return f'{value:,}'.replace(',', ' ')


def percentages(weights):
    """Tenths of a percent, distributed so the displayed sum is 100%."""
    total = sum(weights)
    exact = [Decimal(str(w)) * 1000 / Decimal(str(total)) for w in weights]
    units = [int(x.to_integral_value(rounding=ROUND_FLOOR)) for x in exact]
    for i in sorted(range(3), key=lambda i: exact[i] - units[i], reverse=True)[:1000 - sum(units)]:
        units[i] += 1
    return [u / 10 for u in units]


def pct(value):
    return f'{value:.1f}'.replace('.', ',')


def sentiment(panel):
    return [Decimal(re.search(r'(\d+(?:[.,]\d+)?)%', n.text())[1].replace(',', '.')) for n in panel.find('bar-meta')]


def sample_size(panel):
    pills = panel.find('stat-pill')
    sample = next(n for n in pills if 'После фильтрации:' in n.text() or 'Сохранённая выборка:' in n.text())
    return number(sample.text())


def render_sentiment(values, total):
    """Use the same percentages for bars, legend and SVG arc geometry."""
    circumference = 2 * 3.141592653589793 * 56
    result = ['<div class="sentiment-row">', '  <div class="bar-group">']
    for label, color, value in zip(LABELS, COLORS, values):
        result.extend([
            '    <div class="bar-row">',
            f'      <div class="bar-meta"><span class="lbl" style="color:var(--{color})">{label}</span><span class="pct">≈{pct(value)}%</span></div>',
            f'      <div class="bar-track"><div class="bar-fill {color}" style="width:{value:.1f}%"></div></div>',
            '    </div>',
        ])
    result.extend(['  </div>', '  <div class="donut-wrap">', '    <svg width="164" height="164" viewBox="0 0 164 164" role="img" aria-label="Оценка тональности сообщений">',
                   '      <circle cx="82" cy="82" r="56" fill="none" stroke="var(--surface2)" stroke-width="20"/>'])
    offset = 0.0
    for color, value in zip(COLORS, values):
        length = circumference * value / 100
        result.append(f'      <circle cx="82" cy="82" r="56" fill="none" stroke="var(--{color})" stroke-width="20" stroke-dasharray="{length:.2f} {circumference-length:.2f}" stroke-dashoffset="{-offset:.2f}" transform="rotate(-90 82 82)"/>')
        offset += length
    result.extend([f'      <text x="82" y="78" text-anchor="middle" class="donut-center-text">{total}</text>',
                   '      <text x="82" y="93" text-anchor="middle" class="donut-center-sub">сообщений</text>',
                   '    </svg>', '    <div class="legend">'])
    for label, color, value in zip(LABELS, COLORS, values):
        result.append(f'      <div class="legend-item"><div class="legend-dot" style="background:var(--{color})"></div>{label} — ≈{pct(value)}%</div>')
    result.extend(['    </div>', '  </div>', '</div>'])
    return '\n'.join(result)


def reconcile(source):
    edits = []
    stream_panels = []
    for key, group in groups(source).items():
        panels = group.find('panel')
        streams = [p for p in panels if 'Дата' in cards(p)]
        stream_panels.extend(streams)
        summaries = [p for p in panels if 'Дата' not in cards(p)]
        for summary in summaries:
            if summary.attrs.get("data-chat-exact") == "true":
                continue  # Exact summaries are rendered directly from message counts.
            # August's summary is explicitly the seven Community Cast streams.
            selected = streams[1:8] if key == 'group-aug' else streams
            selected = [p for p in selected if p.find('bar-meta')]
            sizes = [sample_size(p) for p in selected]
            raw_total = sum(number(next(n.text() for n in p.find('stat-pill')
                                        if 'Всего сообщений:' in n.text())) for p in selected)
            weights = [sum(Decimal(n) * sentiment(p)[i] / 100 for n, p in zip(sizes, selected)) for i in range(3)]
            values = percentages(weights)
            old = summary.find('sentiment-row')[0]
            edits.append((old.start, old.end, render_sentiment(values, '~' + fmt(sum(sizes)))))
            for pill in summary.find('stat-pill'):
                if 'Значимых' in pill.text():
                    label = 'Значимых' if key == 'group-aug' else 'Значимых сообщений'
                    edits.append((pill.start, pill.end, f'<div class="stat-pill">{label}: <span>~{fmt(sum(sizes))}</span></div>'))
                elif 'Флуд в среднем:' in pill.text() or 'Исключено, оценка:' in pill.text():
                    removed = 100 * (raw_total - sum(sizes)) / raw_total
                    edits.append((pill.start, pill.end,
                                  f'<div class="stat-pill">Исключено, оценка: <span>~{pct(removed)}%</span></div>'))
                elif 'Всего сообщений:' in pill.text():
                    edits.append((pill.start, pill.end,
                                  f'<div class="stat-pill">Всего сообщений: <span>~{fmt(raw_total)}</span></div>'))
            note = ('<div class="note"><strong>Расчёт тональности:</strong> оценка по '
                    f'{len(selected)} эфирам, взвешенная по числу сообщений после прежней фильтрации. '
                    'Доля исключённых сообщений рассчитана от суммы исходных сообщений этих эфиров. '
                    'Исходные размеры выборок и проценты приблизительные; повторная разметка чатов не проводилась. '
                    'Позитив, нейтраль и негатив относятся к общей тональности сообщений, включая реакции на гостей, игру и эфир.</div>')
            existing = next((n for n in summary.find('note') if n.text().startswith('Расчёт тональности:')), None)
            if existing:
                edits.append((existing.start, existing.end, note))
            else:
                edits.append((old.start, old.start, note + '\n'))
    followers = sum(number(cards(p)['Новые фолловеры']) for p in stream_panels)
    with_chat = [p for p in stream_panels if p.find('bar-meta')]
    assert with_chat, 'No stream chat estimates found'
    for panel in with_chat:
        values = sentiment(panel)
        assert len(values) == 3 and sum(values) == 100, 'Stream sentiment must total 100%'
        assert sample_size(panel) > 0, 'Missing chat sample size'
    overview = groups(source)['group-overview']
    text = source[overview.start:overview.end]
    text, count = re.subn(
        r'(>Новых фолловеров</div>\s*<div[^>]*>)[\d ]+(</div>)',
        lambda match: match[1] + fmt(followers) + match[2], text)
    assert count == 1 or (count == 0 and 'Фолловеров на канале</div>' in text), 'Overview follower card not found'
    avg = percentages([sum(sentiment(p)[i] for p in with_chat) for i in range(3)])
    # Equal weight per stream preserves the overview's meaning of an average stream.
    old_values = re.findall(r'<span style="color:var\(--muted\);">~([\d.,]+)%</span>', text)
    if old_values:
        assert len(old_values) == 3
        iterator = iter(avg)
        text = re.sub(r'<span style="color:var\(--muted\);">~[\d.,]+%</span>',
                      lambda m: f'<span style="color:var(--muted);">~{pct(next(iterator))}%</span>', text)
        for color, value in zip(COLORS, avg):
            text = re.sub(r'width:[\d.]+%;height:100%;background:var\(--' + color + r'\)',
                          f'width:{value:.1f}%;height:100%;background:var(--{color})', text)
        edits.append((overview.start, overview.end, text))
    # Apply insertions after replacements at the same offset.
    for start, end, replacement in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        source = source[:start] + replacement + source[end:]
    return source


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'index.html'
    before = path.read_text()
    after = reconcile(before)
    if args.write:
        path.write_text(after)
        print('Updated derived chat summaries and total new follows.')
    elif after != before:
        raise SystemExit('Derived chat summaries are out of date. Run with --write.')
    else:
        print('Derived chat summaries and total new follows agree with stream cards.')
