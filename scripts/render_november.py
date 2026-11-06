"""Render the approved November stream with an explicit engagement metric.

Only aggregates and anonymous selected quotations enter the public dashboard.
"""
import argparse
from html import escape
import json
from pathlib import Path
import re

from dashboard_html import groups
from reconcile_dashboard import percentages, pct, render_sentiment
from sync_statistics import card, statistics, fmt

ROOT = Path(__file__).resolve().parents[1]


def chat_section(chat):
    counts = [chat['counts'][k] for k in ['positive', 'neutral', 'negative']]
    assert sum(counts) == chat['retained_messages']
    assert chat['raw_messages'] - chat['excluded_messages'] == sum(counts)
    assert sum(chat['positive_breakdown'].values()) == counts[0]
    values = percentages(counts)
    out = ['<div class="section-label">Реакция чата · позитив и вовлечение</div>', '<div class="stats-row">']
    for label, value in [('Всего сообщений', chat['raw_messages']), ('После фильтрации', sum(counts)), ('Исключено', chat['excluded_messages'])]:
        out.append(f'<div class="stat-pill">{label}: <span>{fmt(value)}</span></div>')
    out += ['</div>', f'<div class="note"><strong>Как считаем:</strong> {escape(chat["methodology"])}</div>']
    chart = render_sentiment(values, fmt(sum(counts))).replace('≈', '')
    chart = chart.replace('Позитив', 'Позитив и вовлечение').replace('Оценка тональности сообщений', 'Реакция чата: позитив и вовлечение, нейтраль, негатив')
    for value, count in zip(values, counts):
        chart = chart.replace(f'<span class="pct">{pct(value)}%</span>', f'<span class="pct">{pct(value)}% · {fmt(count)} сообщений</span>')
    out += [chart, f'<div class="note"><strong>Учёт вовлечения:</strong> {escape(chat["methodology_note"])}</div>',
            '<details class="note"><summary>Очистка чата и особенности анализа</summary>',
            f'<p>{escape(chat["cleanup_note"])}</p><p>{escape(chat["limitation_note"])}</p></details>']
    return '\n'.join(out)


def render(source):
    records = [r for r in json.loads((ROOT / 'data/streams.json').read_text())['records'] if r['group'] == 'group-nov']
    assert len(records) == 1, 'Extend the November renderer before adding another stream.'
    r = records[0]
    chat = json.loads((ROOT / 'data/stream-2026-11-05.json').read_text())
    assert chat['status'] == 'approved' and chat['stream_id'] == r['id']
    title = escape(r['title'])
    date = card('Дата', r['display_date'], title).replace('class="card-value"', 'class="card-value accent" style="font-size:17px"', 1)
    out = ['<div class="month-group" id="group-nov">', '<div class="stream-tabs">',
           f'<button class="tab active" onclick="switchTab(\'nov\',0)">5 ноября · {title}</button>',
           '<button class="tab summary" onclick="switchTab(\'nov\',1)">Итоги ноября</button>', '</div>',
           '<div class="panel active" data-chat-exact="true" data-chat-method="positive-engagement">',
           statistics(r, date).rstrip(), '<hr class="divider">',
           f'<div class="note"><strong>{title}.</strong> За кулисами даркстора: сборка заказов, работа команды и доставка роверами. <a href="{escape(chat["video_url"])}" target="_blank" rel="noopener noreferrer" style="color:var(--accent3)">Смотреть запись ↗</a></div>',
           '<div class="raids"><span class="raids-label">Рейды</span>']
    for raid in chat['raids']:
        h, rem = divmod(raid['offset_seconds'], 3600)
        m, s = divmod(rem, 60)
        time = f'{h}:{m:02}:{s:02}' if h else f'{m}:{s:02}'
        out.append(f'<span class="raid-pill"><span class="raid-who">{escape(raid["channel"])}</span><span class="raid-num">{fmt(raid["viewers_reported_by_twitch"])}</span><span class="raid-time">{time}</span></span>')
    out += ['</div>', chat_section(chat), '<div class="section-label">Характерные комментарии</div>', '<div class="quotes-grid">']
    for q in chat['quotes']:
        mark = {'pos': '+', 'neu': '○', 'neg': '−'}[q['label']]
        out.append(f'<div class="q-card"><span class="q-badge {q["label"]}">{mark}</span>{escape(q["text"])}<div class="q-source">{escape(q["caption"])}</div></div>')
    out += ['</div>', '<div class="feedback"><div class="feedback-title">Обратная связь команды</div>']
    out += [f'<p>{escape(p)}</p>' for p in chat['feedback']]
    out += ['</div>', '</div>', '<div class="panel" data-chat-exact="true" data-chat-method="positive-engagement">',
            '<div class="section-label">Итоги ноября · канал Яндекса</div>', '<div class="cards">',
            card('Эфиров', '1'), card('Просмотры (наш канал)', fmt(r['own']['views'])),
            card('Минут просмотра', fmt(r['own']['minutes'])), card('Пиковый онлайн', fmt(r['own']['peak'])),
            card('Средний онлайн', fmt(r['own']['average'])), card('Новые фолловеры', fmt(r['own']['follows'])),
            '</div>', '<hr class="divider">',
            '<div class="note">В дашборд внесён один ноябрьский эфир, 5 ноября. Сводка отражает этот эфир и обновится при добавлении следующих.</div>',
            chat_section(chat), '</div>', '</div>']
    html = '\n'.join(out)
    old = groups(source).get('group-nov')
    if old:
        source = source[:old.start] + html + source[old.end:]
    else:
        anchor = groups(source)['group-audience'].start
        source = source[:anchor] + html + '\n\n' + source[anchor:]
        marker = '  <button class="month-tab" onclick="switchMonth(\'oct\')">Октябрь · 1 стрим</button>\n'
        assert source.count(marker) == 1
        source = source.replace(marker, marker + '  <button class="month-tab" onclick="switchMonth(\'nov\')">Ноябрь · 1 стрим</button>\n')
    count = len(json.loads((ROOT / 'data/streams.json').read_text())['records'])
    return re.sub(r'Мониторинг Twitch-трансляций · \d+ стрим\w*', f'Мониторинг Twitch-трансляций · {count} стримов', source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'index.html'
    before = path.read_text()
    after = render(before)
    if args.write:
        path.write_text(after)
        print('Rendered approved November stream and summary.')
    elif before != after:
        raise SystemExit('November is out of sync. Run with --write.')
    else:
        print('November agrees with approved source data.')
