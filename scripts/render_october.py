"""Render the approved October stream and its monthly summary from aggregate data.

Raw replay chat and individual author identifiers stay outside the public repo.
"""
import argparse
from html import escape
import json
from pathlib import Path

from dashboard_html import groups
from reconcile_dashboard import percentages, pct, render_sentiment
from sync_statistics import card, statistics, fmt

ROOT = Path(__file__).resolve().parents[1]


def chat_section(chat):
    counts = list(chat['counts'].values())
    assert list(chat['counts']) == ['positive', 'neutral', 'negative']
    assert sum(counts) == chat['retained_messages']
    assert chat['raw_messages'] - chat['excluded_messages'] == sum(counts)
    assert sum(chat['exclusion_reasons'].values()) == chat['excluded_messages']
    values = percentages(counts)
    out = ['<div class="section-label">Анализ чата · общая тональность</div>', '<div class="stats-row">']
    for label, value in [('Всего сообщений', chat['raw_messages']), ('После фильтрации',sum(counts)), ('Исключено',chat['excluded_messages'])]:
        out.append(f'<div class="stat-pill">{label}: <span>{fmt(value)}</span></div>')
    out += ['</div>', '<div class="note"><strong>Методика:</strong> из анализа исключены бот-анонсы, системные события, ответы официального канала, приветствия, эмоуты и бессодержательные повторы. Каждое оставшееся сообщение размечено по общей тональности, включая реакции на ведущих, сюжет, продукты и качество эфира. Поддержка, доброжелательные шутки и выраженный интерес учтены в позитиве. Информационные вопросы без оценки остаются нейтральными.</div>']
    chart = render_sentiment(values, fmt(sum(counts))).replace('≈','')
    for value, count in zip(values,counts):
        chart = chart.replace(f'<span class="pct">{pct(value)}%</span>', f'<span class="pct">{pct(value)}% · {fmt(count)} сообщений</span>')
    out += [chart, '<div class="note"><strong>Нейтраль и вовлечение:</strong> нейтральные сообщения включают вопросы, обсуждение поиска самокатов, устройства техники и работы команды.</div>']
    return '\n'.join(out)


def render(source):
    data=json.loads((ROOT/'data/streams.json').read_text())
    records=[r for r in data['records'] if r['group']=='group-oct']
    assert len(records)==1, 'Extend the October renderer before adding another stream.'
    r=records[0]
    chat=json.loads((ROOT/'data/stream-2026-10-29.json').read_text())
    assert chat['status']=='approved' and chat['stream_id']==r['id']
    title=escape(r['title'])
    date=card('Дата',r['display_date'],title)
    out=['<div class="month-group" id="group-oct">', '<div class="stream-tabs">',f'<button class="tab active" onclick="switchTab(\'oct\',0)">29 октября · {title}</button>', '<button class="tab summary" onclick="switchTab(\'oct\',1)">Итоги октября</button>', '</div>', '<div class="panel active" data-chat-exact="true">', statistics(r,date).rstrip(), '<hr class="divider">',f'<div class="note"><strong>{title}.</strong> IRL-поиск и извлечение потерянных самокатов. <a href="{chat["video_url"]}" target="_blank" rel="noopener noreferrer" style="color:var(--accent3)">Смотреть запись ↗</a></div>','<div class="raids"><span class="raids-label">Рейды</span>']
    for raid in chat['raids']:
        if raid['channel'] not in {'evikey', 'Terablade'}:
            continue  # Only the two selected raids are displayed.
        h, rem=divmod(raid['offset_seconds'],3600)
        m,s=divmod(rem,60)
        time=f'{h}:{m:02}:{s:02}' if h else f'{m}:{s:02}'
        out.append(f'<span class="raid-pill"><span class="raid-who">{escape(raid["channel"])}</span><span class="raid-num">{fmt(raid["viewers_reported_by_twitch"])}</span><span class="raid-time">{time}</span></span>')
    out += ['</div>',chat_section(chat),'<div class="section-label">Примеры сообщений</div>','<div class="quotes-grid">']
    for q in chat['quotes']:
        label={'pos':'+','neu':'○','neg':'−'}[q['label']]
        out.append(f'<div class="q-card"><span class="q-badge {q["label"]}">{label}</span>{escape(q["text"])}</div>')
    out += ['</div>','<div class="feedback"><div class="feedback-title">Обратная связь команды</div>']
    out += [f'<p>{escape(p)}</p>' for p in chat['feedback']]
    out += ['</div>','</div>','<div class="panel" data-chat-exact="true">','<div class="section-label">Итоги октября · канал Яндекса</div>','<div class="cards">', card('Эфиров','1'), card('Просмотры (наш канал)',fmt(r['own']['views'])),card('Минут просмотра',fmt(r['own']['minutes'])),card('Пиковый онлайн',fmt(r['own']['peak'])),card('Средний онлайн',fmt(r['own']['average'])),card('Новые фолловеры',fmt(r['own']['follows'])),'</div>','<hr class="divider">','<div class="note">В дашборд внесён один октябрьский эфир, 29 октября. Сводка отражает только этот эфир и обновится при добавлении следующих.</div>',chat_section(chat),'</div>','</div>']
    html='\n'.join(out)
    old=groups(source).get('group-oct')
    if old:
        return source[:old.start]+html+source[old.end:]
    anchor=groups(source)['group-audience'].start
    source=source[:anchor]+html+'\n\n'+source[anchor:]
    nav='  <button class="month-tab" onclick="switchMonth(\'oct\')">Октябрь · 1 стрим</button>\n'
    marker='  <button class="month-tab" onclick="switchMonth(\'sep\')">Сентябрь · 5 стримов</button>\n'
    assert source.count(marker)==1
    source=source.replace(marker,marker+nav)
    return source.replace('Мониторинг Twitch-трансляций · 34 стрима','Мониторинг Twitch-трансляций · 35 стримов')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    path=ROOT/'index.html'
    before=path.read_text()
    after=render(before)
    if args.write:
        path.write_text(after)
        print('Rendered approved October stream and summary.')
    elif before!=after:
        raise SystemExit('October is out of sync. Run with --write.')
    else:
        print('October agrees with approved source data.')
