"""Render channel statistics and collaboration cards from data/streams.json.

Run with --write to update index.html. Without it, check synchronization.
Historical chat analysis and editorial feedback are left intact.
"""
import argparse
import json
from pathlib import Path
import re

from dashboard_html import groups, cards, Parser

ROOT = Path(__file__).resolve().parents[1]
OWN_LABELS = [
    ('views', 'Просмотры'), ('unique', 'Уникальные зрители'),
    ('minutes', 'Минут просмотра'), ('peak', 'Макс. онлайн'),
    ('average', 'Средний онлайн'), ('duration', 'Длительность'),
    ('follows', 'Новые фолловеры'),
]


def fmt(value):
    return f'{value:,}'.replace(',', ' ')


def card(label, value, sub=None, highlight=False):
    classes = 'card highlight' if highlight else 'card'
    small = f'<div class="card-sub">{sub}</div>' if sub else ''
    return (f'<div class="{classes}"><div class="card-label">{label}</div>'
            f'<div class="card-value">{value}</div>{small}</div>')


def collaboration_cards(record):
    """Preserve every historical card; refresh views with the channel source."""
    result = []
    for html in record['historical_collaboration_cards']:
        node = Parser(html).root.find('card')[0]
        if node.find('card-label')[0].text() == 'Просмотры (всего)':
            sub = node.find('card-sub')[0].text()
            own = re.search(r'наши\s+(\d[\d ]*)', sub)
            assert own, f"Missing channel breakdown: {record['id']}"
            # Keep every partner value. Only the channel component has changed.
            partner_views = sum(int(re.sub(r'\D', '', number))
                                for number in re.findall(r'\+\s*[^+]*?\s(\d[\d ]*)(?=\+|$)', sub))
            assert partner_views > 0
            total = record['own']['views'] + partner_views
            html = re.sub(r'(<div class="card-value">)[\d ]+(</div>)',
                          lambda m: m[1] + fmt(total) + m[2], html, count=1)
            html = re.sub(r'наши\s+\d[\d ]*(?=\+)',
                          'наши ' + fmt(record['own']['views']) + ' ', html, count=1)
        result.append(html)
    return result


def statistics(record, date_card):
    collaboration = collaboration_cards(record)
    own = [card(label + (' (наш канал)' if key == 'average' and collaboration else ''),
                fmt(record['own'][key]) + (' мин' if key == 'duration' else ''))
           for key, label in OWN_LABELS]
    if record['show_chat_unique'] and record['own']['chat_unique'] is not None:
        own.append(card('Уник. зрители (чат)', fmt(record['own']['chat_unique'])))
    if collaboration:
        return ('<div class="section-label">Данные стрима</div>\n'
                '<div class="cards">\n' + date_card + '\n' + '\n'.join(collaboration) + '\n</div>\n'
                '<div class="section-label">Канал Яндекса</div>\n'
                '<div class="cards cards-own">\n' + '\n'.join(own) + '\n</div>\n'
                '<div class="statistics-note">Общие показатели учитывают коллаборацию. '
                'Уникальные зрители разных каналов могут пересекаться, а пики онлайна — приходиться на разное время. '
                'Показатели канала Яндекса приведены отдельно по сводной таблице.</div>\n')
    return ('<div class="section-label">Данные стрима · канал Яндекса</div>\n'
            '<div class="cards">\n' + date_card + '\n' + '\n'.join(own) + '\n</div>\n')


def reconcile(source):
    data = json.loads((ROOT / 'data/streams.json').read_text())
    by_date = {record['display_date']: record for record in data['records']}
    assert len(by_date) == len(data['records'])
    edits = []
    selected = set()
    for gid, group in groups(source).items():
        streams = [p for p in group.find('panel') if 'Дата' in cards(p)]
        for panel in streams:
            record = by_date[cards(panel)['Дата']]
            assert record['group'] == gid
            selected.add(record['id'])
            date_node = next(c for c in panel.find('card') if c.find('card-label')[0].text() == 'Дата')
            # Replace only statistics above the first divider. Chat and feedback follow it.
            label = panel.find('section-label')[0]
            divider = next(n for n in panel.walk() if n.tag == 'hr')
            edits.append((label.start, divider.start,
                          statistics(record, source[date_node.start:date_node.end])))
        summaries = [p for p in group.find('panel') if 'Дата' not in cards(p)]
        for summary in summaries:
            records = [by_date[cards(p)['Дата']] for p in streams]
            if gid == 'group-aug':
                records = records[1:8]  # Community Cast only, not the entire month.
            totals = {key: sum(r['own'][key] for r in records)
                      for key in ['views', 'unique', 'minutes', 'duration', 'follows']}
            peak = max(r['own']['peak'] for r in records)
            for node in summary.find('card'):
                label = node.find('card-label')[0].text()
                mapping = {'Просмотры (всего)': 'views', 'Просмотры (наш канал)': 'views',
                           'Уникальные зрители': 'unique', 'Минут просмотра': 'minutes',
                           'Новые фолловеры': 'follows'}
                html = source[node.start:node.end]
                if label in mapping:
                    html = replace_value(html, fmt(totals[mapping[label]]))
                elif gid != 'group-aug' and label in ['Пиковый онлайн', 'Макс. общий онлайн']:
                    html = replace_value(html, fmt(peak)).replace('Макс. общий онлайн', 'Пиковый онлайн')
                    html = html.replace(' · коллаб', ' · канал Яндекса')
                elif gid == 'group-aug' and label == 'Просмотры (всего с коллабами)':
                    total = 0
                    for record in records:
                        for fragment in collaboration_cards(record):
                            n = Parser(fragment).root.find('card')[0]
                            if n.find('card-label')[0].text() == 'Просмотры (всего)':
                                total += int(re.sub(r'\D', '', n.find('card-value')[0].text()))
                    html = replace_value(html, fmt(total))
                if html != source[node.start:node.end]:
                    edits.append((node.start, node.end, html))
    assert len(selected) == len(data['records'])
    # Overview always covers the channel alone, across the entire period.
    overview = groups(source)['group-overview']
    text = source[overview.start:overview.end]
    follows = sum(r['own']['follows'] for r in data['records'])
    text, count = re.subn(r'(>Новых фолловеров</div>\s*<div[^>]*>)[\d ]+(</div>)',
                         lambda m: m[1] + fmt(follows) + m[2], text)
    assert count == 1
    if text != source[overview.start:overview.end]:
        edits.append((overview.start, overview.end, text))
    for start, end, replacement in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        source = source[:start] + replacement + source[end:]
    return source


def replace_value(html, value):
    result, count = re.subn(r'(<div class="card-value[^\"]*"[^>]*>)[^<]+(</div>)',
                            lambda m: m[1] + value + m[2], html, count=1)
    assert count == 1
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'index.html'
    before = path.read_text()
    after = reconcile(before)
    if args.write:
        path.write_text(after)
        print('Updated channel statistics; preserved collaboration cards and chat analysis.')
    elif after != before:
        raise SystemExit('Statistics differ from data/streams.json. Run with --write.')
    else:
        print('All 34 stream statistics and derived totals agree with source data.')
