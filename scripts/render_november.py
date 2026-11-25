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


def stream_panel(r, chat, active):
    assert chat['status'] == 'approved' and chat['stream_id'] == r['id']
    title = escape(r['title'])
    date = card('Дата', r['display_date'], title).replace('class="card-value"', 'class="card-value accent" style="font-size:17px"', 1)
    description = chat.get('description', 'За кулисами даркстора: сборка заказов, работа команды и доставка роверами.')
    out = [f'<div class="panel{" active" if active else ""}" data-chat-exact="true" data-chat-method="positive-engagement">',
           statistics(r, date).rstrip(), '<hr class="divider">',
           f'<div class="note"><strong>{title}.</strong> {escape(description)} <a href="{escape(chat["video_url"])}" target="_blank" rel="noopener noreferrer" style="color:var(--accent3)">Смотреть запись ↗</a></div>']
    if chat['raids']:
        out.append('<div class="raids"><span class="raids-label">Рейды</span>')
    for raid in chat['raids']:
        h, rem = divmod(raid['offset_seconds'], 3600)
        m, s = divmod(rem, 60)
        time = f'{h}:{m:02}:{s:02}' if h else f'{m}:{s:02}'
        out.append(f'<span class="raid-pill"><span class="raid-who">{escape(raid["channel"])}</span><span class="raid-num">{fmt(raid["viewers_reported_by_twitch"])}</span><span class="raid-time">{time}</span></span>')
    if chat['raids']:
        out.append('</div>')
    out += [chat_section(chat), '<div class="section-label">Характерные комментарии</div>', '<div class="quotes-grid">']
    for q in chat['quotes']:
        mark = {'pos': '+', 'neu': '○', 'neg': '−'}[q['label']]
        out.append(f'<div class="q-card"><span class="q-badge {q["label"]}">{mark}</span>{escape(q["text"])}<div class="q-source">{escape(q["caption"])}</div></div>')
    out += ['</div>', '<div class="feedback"><div class="feedback-title">Обратная связь команды</div>']
    out += [f'<p>{escape(p)}</p>' for p in chat['feedback']]
    out += ['</div>', '</div>']
    return '\n'.join(out)


def render(source):
    records = [r for r in json.loads((ROOT / 'data/streams.json').read_text())['records'] if r['group'] == 'group-nov']
    chats = [json.loads((ROOT / f'data/stream-{r["sheet_date"]}.json').read_text()) for r in records]
    out = ['<div class="month-group" id="group-nov">', '<div class="stream-tabs">']
    for i, r in enumerate(records):
        short_date = r['display_date'].removesuffix(' 2026')
        out.append(f'<button class="tab{" active" if i == 0 else ""}" onclick="switchTab(\'nov\',{i})">{escape(short_date)} · {escape(r["title"])}</button>')
    out += [f'<button class="tab summary" onclick="switchTab(\'nov\',{len(records)})">Итоги ноября</button>', '</div>']
    out += [stream_panel(r, chat, i == 0) for i, (r, chat) in enumerate(zip(records, chats))]
    totals = {k: sum(r['own'][k] for r in records) for k in ['views','minutes','duration','follows']}
    average = round(sum(r['own']['average'] * r['own']['duration'] for r in records) / totals['duration'])
    emotional = [sum(chat['emotional_counts'][k] for chat in chats) for k in ['positive','neutral','negative']]
    retained = sum(chat['retained_messages'] for chat in chats)
    assert sum(emotional) == retained
    out += ['<div class="panel" data-chat-exact="true">',
            '<div class="section-label">Итоги ноября · канал Яндекса</div>', '<div class="cards">',
            card('Эфиров', str(len(records))), card('Просмотры (наш канал)', fmt(totals['views'])),
            card('Минут просмотра', fmt(totals['minutes'])), card('Пиковый онлайн', fmt(max(r['own']['peak'] for r in records))),
            card('Средний онлайн', fmt(average), 'взвешен по длительности эфиров'), card('Новые фолловеры', fmt(totals['follows'])),
            '</div>', '<hr class="divider">',
            '<div class="section-label">Эмоциональная тональность · без добавления вовлечения</div>',
            '<div class="note">Для сравнимой месячной сводки объединены исходные эмоциональные оценки сообщений. Вовлечение отдельно показано на вкладках эфиров: 24 ноября его определение расширено и включает участие в заданиях ведущего. Разные определения вовлечения в общий процент не объединяются.</div>',
            '<div class="stats-row">',
            f'<div class="stat-pill">Всего сообщений: <span>{fmt(sum(c["raw_messages"] for c in chats))}</span></div>',
            f'<div class="stat-pill">После фильтрации: <span>{fmt(retained)}</span></div>',
            f'<div class="stat-pill">Исключено: <span>{fmt(sum(c["excluded_messages"] for c in chats))}</span></div>',
            '</div>', render_sentiment(percentages(emotional), fmt(retained)).replace('≈', ''), '</div>', '</div>']
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
    source = re.sub(r'(onclick="switchMonth\(\'nov\'\)">)Ноябрь · \d+ стрим\w*', lambda m: m[1] + f'Ноябрь · {len(records)} стрима', source)
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
