"""Render only the overview from verified stream statistics and saved chat estimates."""
import argparse
from decimal import Decimal, ROUND_HALF_UP
from html import escape
import json
from pathlib import Path
import re

from dashboard_html import Parser, groups, cards
from reconcile_dashboard import sentiment, percentages, pct
from sync_statistics import collaboration_cards

ROOT = Path(__file__).resolve().parents[1]
MONTHS = {'apr': 'Апрель', 'may': 'Май', 'jun': 'Июнь', 'jul': 'Июль', 'aug': 'Август', 'sep': 'Сентябрь'}


def fmt(n):
    return f'{n:,}'.replace(',', ' ')


def rounded(n):
    return int(Decimal(str(n)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def metric(label, value, sub, accent=False):
    return f'<div class="ov-metric{ " ov-accent" if accent else ""}"><div class="ov-label">{label}</div><div class="ov-value">{value}</div><div class="ov-sub">{sub}</div></div>'


def heading(kicker, title, description=''):
    return f'<div class="ov-heading"><div class="section-label">{kicker}</div><h2>{title}</h2>{f"<p>{description}</p>" if description else ""}</div>'


def render(source):
    data = json.loads((ROOT / 'data/streams.json').read_text())
    records = data['records']
    own = lambda key: sum(r['own'][key] for r in records)
    avg = lambda rs: sum(r['own']['average'] * r['own']['duration'] for r in rs) / sum(r['own']['duration'] for r in rs)
    collabs = [r for r in records if r['sheet_date'] >= '2026-08-01' and r['historical_collaboration_cards']]
    combined = 0
    partners = set()
    for r in collabs:
        for html in collaboration_cards(r):
            n = Parser(html).root.find('card')[0]
            if n.find('card-label')[0].text() == 'Просмотры (всего)':
                combined += int(re.sub(r'\D', '', n.find('card-value')[0].text()))
                for term in n.find('card-sub')[0].text().split('+')[1:]:
                    partners.add(re.sub(r'\s+\d[\d ]*$', '', term.strip()))
    collab_own = sum(r['own']['views'] for r in collabs)
    out = ['<div class="month-group active" id="group-overview">']
    out += [heading('Апрель — сентябрь 2026', 'Результаты канала Яндекса', f'{len(records)} эфира · показатели нашего канала за весь период')]
    out += ['<div class="ov-kpis">',
            metric('Эфиров', str(len(records)), 'апрель — сентябрь 2026'),
            metric('Просмотров', fmt(own('views')), 'на канале Яндекса'),
            metric('Часов просмотра', fmt(rounded(own('minutes') / 60)), f"{fmt(own('minutes'))} минут · округлено до часа"),
            metric('Средний онлайн', fmt(rounded(avg(records))), 'взвешен по длительности эфиров'),
            metric('Новых фолловеров', fmt(own('follows')), 'сумма новых подписок за эфиры'), '</div>',
            '<p class="ov-footnote">На канале ≈24 527 фолловеров — по данным команды на 23.10.2026. Текущий размер аудитории отличается от суммы новых подписок за эфиры.</p>']
    out += ['<section class="ov-section" aria-labelledby="ov-collabs">',
            heading('Август — сентябрь 2026', '<span id="ov-collabs">Масштаб коллабораций</span>', 'Совместные эфиры, для которых внесены просмотры партнёрских каналов'),
            '<div class="ov-collab-kpis">',
            metric('Просмотры всех каналов', fmt(combined), 'наш канал + каналы партнёров', True),
            metric('Наш канал', fmt(collab_own), 'на этих же совместных эфирах'),
            metric('Совместных эфиров', str(len(collabs)), 'с внесённой статистикой партнёров'),
            metric('Партнёрских каналов', str(len(partners)), 'уникальных каналов в этой выборке'), '</div>',
            '<div class="ov-partners">' + ''.join(f'<span>{escape(p)}</span>' for p in sorted(partners, key=str.casefold)) + '</div>',
            '<p class="ov-footnote">Общие просмотры уже включают наш канал: их нельзя прибавлять к просмотрам в верхнем блоке. Это сумма просмотров, а не уникальный охват. Коллаборации до августа в этот блок не входят.</p></section>']
    out += ['<section class="ov-section" aria-labelledby="ov-dynamics">', heading('По месяцам', '<span id="ov-dynamics">Динамика нашего канала</span>', 'Одинаковая методика за весь период · без показателей партнёров'), '<div class="ov-chart-grid">']
    buckets = [(month, [r for r in records if r['group'] == 'group-' + month]) for month in MONTHS]
    for key, title, unit in [('views', 'Просмотры', 'просмотров'), ('average', 'Средний онлайн', 'зрителей')]:
        values = [sum(r['own']['views'] for r in rs) if key == 'views' else rounded(avg(rs)) for _, rs in buckets]
        maximum = max(values)
        out += [f'<div class="ov-chart"><h3>{title}</h3><div class="ov-bars" role="group" aria-label="{title} по месяцам">']
        for (month, rs), value in zip(buckets, values):
            label = f'{MONTHS[month]}: {fmt(value)} {unit}, эфиров: {len(rs)}'
            out.append(f'<button type="button" class="ov-bar" onclick="switchMonth(\'{month}\')" aria-label="{label}. Открыть месяц" title="{label}"><span class="ov-bar-value">{fmt(value)}</span><span class="ov-bar-area"><span class="ov-bar-fill" style="height:{value / maximum * 100:.2f}%"></span></span><span class="ov-bar-month">{MONTHS[month]}</span><span class="ov-bar-count">{len(rs)} эф.</span></button>')
        out += ['</div></div>']
    out += ['</div><p class="ov-footnote">Просмотры суммируются. Средний онлайн рассчитан из средних значений эфиров в исходной таблице с весом по длительности каждого эфира. Число эфиров и длительность месяцев различаются.</p></section>']
    out += ['<section class="ov-section" aria-labelledby="ov-best">', heading('Лидеры за весь период', '<span id="ov-best">Лучшие эфиры</span>', 'По показателям нашего канала · нажмите на карточку, чтобы открыть эфир'), '<div class="ov-best-grid">']
    for key, label, unit in [('views', 'Больше всего просмотров', 'просмотров'), ('minutes', 'Больше всего часов просмотра', 'часов просмотра'), ('follows', 'Больше всего новых фолловеров', 'новых фолловеров')]:
        winner = max(records, key=lambda r: r['own'][key])
        month = winner['group'].removeprefix('group-')
        idx = [r for r in records if r['group'] == winner['group']].index(winner)
        value = rounded(winner['own'][key] / 60) if key == 'minutes' else winner['own'][key]
        title = winner['title']
        out.append(f'<button type="button" class="ov-best" onclick="switchMonth(\'{month}\');switchTab(\'{month}\',{idx})"><span class="ov-label">{label}</span><span class="ov-value">{fmt(value)}</span><span class="ov-sub">{unit}</span><span class="ov-best-title">{escape(title)}</span><span class="ov-best-date">{winner["display_date"]}</span><span class="ov-link">Открыть эфир ↗</span></button>')
    out += ['</div></section>']
    streams = [p for gid,g in groups(source).items() if gid != 'group-overview' for p in g.find('panel') if 'Дата' in cards(p)]
    with_chat = [p for p in streams if p.find('bar-meta')]
    values = percentages([sum(sentiment(p)[i] for p in with_chat) for i in range(3)])
    out += ['<section class="ov-section" aria-labelledby="ov-sentiment">', heading('Общая реакция аудитории', '<span id="ov-sentiment">Тональность чатов</span>', f'{len(with_chat)} из {len(records)} эфиров с аналитикой чата · исторические оценки'), '<div class="ov-sentiment">', '<div class="ov-sentiment-bars">']
    for label,color,value in zip(['Позитив','Нейтраль','Негатив'],['pos','neu','neg'],values):
        out.append(f'<div class="ov-sentiment-item"><div class="ov-sentiment-meta"><span style="color:var(--{color})">{label}</span><span style="color:var(--muted);">~{pct(value)}%</span></div><div class="ov-sentiment-track"><div style="width:{value:.1f}%;height:100%;background:var(--{color})"></div></div></div>')
    out += ['</div><div class="ov-sentiment-context"><h3>Что означают эти доли</h3><p>Среднее процентов по эфирам: каждый эфир имеет одинаковый вес. Это общая тональность чата — реакции на гостей, игру, содержание и качество эфира.</p><p>Чаты 21 апреля и 7 августа отсутствуют и не учтены. Исторические оценки сохранены; повторная разметка в рамках этого обновления не проводилась.</p></div></div></section>', '</div>']
    old = groups(source)['group-overview']
    return source[:old.start] + '\n'.join(out) + source[old.end:]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'index.html'
    before = path.read_text()
    after = render(before)
    if args.write:
        path.write_text(after)
        print('Updated overview only.')
    elif before != after:
        raise SystemExit('Overview is out of sync. Run with --write.')
    else:
        print('Overview agrees with stream statistics and historical sentiment.')
