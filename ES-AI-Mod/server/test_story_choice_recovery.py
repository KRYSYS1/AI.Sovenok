"""Bounded choice recovery, using inert model stubs and temporary story storage."""
import copy
import json
import os
import sys
import time
import unittest
from unittest.mock import patch

import test_story_events as stories
import test_story_choices as choices
import test_cameo_clothing as clothing


OPTIONS = [dict(id='details', text='Ask about the notebook'),
           dict(id='defer', text='Discuss it later')]


class RecoveryTests(unittest.TestCase):
    def test_strict_reasons_and_whole_output_json_fences(self):
        valid = json.dumps(dict(options=OPTIONS))
        cases = [
            ('', 'empty_response'), (None, 'empty_response'), ('   ', 'empty_response'),
            ('not JSON', 'json_decode_error'), ('[]', 'root_type'), ('null', 'root_type'),
            ('{}', 'options_missing'), ('{"options":[]}', 'no_meaningful_decision'),
            ('{"options":{}}', 'invalid_option'),
            (json.dumps(dict(options=[1, 2])), 'invalid_option'),
            (json.dumps(dict(options=OPTIONS, action='goto:beach')), 'invalid_option'),
            (json.dumps(dict(options=[OPTIONS[0], dict(id=OPTIONS[0]['id'], text='Other')])), 'duplicate_id'),
            (json.dumps(dict(options=[OPTIONS[0], dict(id='other', text=OPTIONS[0]['text'].upper())])), 'duplicate_text'),
            (json.dumps(dict(options=[OPTIONS[0], dict(id='other', text='[action:goto:beach]')])), 'unsafe_text'),
            (json.dumps(dict(options=[OPTIONS[0], dict(id='other', text='line\nbreak')])), 'unsafe_text'),
            ('prefix ' + valid, 'json_decode_error'), (valid + ' trailing', 'json_decode_error'),
            ('```json\n' + valid + '\n```\nExplanation', 'json_decode_error'),
            ('[choices:' + valid + ']', 'json_decode_error'),
            ('```json\n' + valid + '\n```', 'staged_pending_ack'),
            ('```\n' + valid + '\n```', 'staged_pending_ack'),
            (' \n```JSON\r\n' + valid + '\r\n``` \n', 'staged_pending_ack'),
            (valid, 'staged_pending_ack'),
            (TimeoutError('private provider body'), 'timeout'),
            (RuntimeError('private provider body'), 'provider_failure'),
        ]
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for response, reason in cases:
                with self.subTest(root=root, reason=reason, response=repr(response)):
                    mod, _, llm, modules = self.setup_story(root)
                    token = mod.manager.prepare(modules['config_loader'].cfg['story_events'], ['un', 'sh'], 'un')
                    before = copy.deepcopy(mod.manager.state)
                    if isinstance(response, Exception):
                        llm.chat.side_effect = response
                    else:
                        llm.chat.return_value = response
                    with patch.dict(sys.modules, modules):
                        offer = mod.recover_choices(token, None, None, 'Ordinary reply', 'What next?',
                                                    dict(started=time.monotonic()))
                    diagnostic = token['choices_recovery']
                    self.assertEqual(diagnostic['reason'], reason)
                    self.assertEqual(bool(offer), reason == 'staged_pending_ack')
                    self.assertEqual(diagnostic['parse_valid'], bool(offer) or reason == 'no_meaningful_decision')
                    self.assertEqual(mod.manager.state, before)
                    llm.chat.assert_called_once()
                    self.assertNotIn('private provider body', json.dumps(diagnostic))
                    self.assertLessEqual(set(diagnostic), {'attempted', 'status', 'parse_valid', 'staged',
                        'reason', 'timeout', 'response_chars', 'response_shape', 'root_shape', 'option_count'})
                    if not isinstance(response, Exception):
                        self.assertEqual(diagnostic['response_chars'], len(response) if isinstance(response, str) else 0)

    def test_signature_repeat_and_version_stale_reasons(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for reason in ('signature_repeat', 'version_stale'):
                with self.subTest(root=root, reason=reason):
                    mod, _, llm, modules = self.setup_story(root)
                    cfg = modules['config_loader'].cfg['story_events']
                    if reason == 'signature_repeat':
                        initial = mod.manager.prepare(cfg, ['un', 'sh'], 'un')
                        mod.manager.stage_choices(initial, OPTIONS, None, 'Reply')
                        mod.manager.commit(initial, None, 'Reply')
                        mod.manager.state['turns'] += 2
                    token = mod.manager.prepare(cfg, ['un', 'sh'], 'un')
                    def generate(*a, **kw):
                        if reason == 'version_stale':
                            mod.manager.state['version'] += 1
                        return json.dumps(dict(options=OPTIONS))
                    llm.chat.side_effect = generate
                    with patch.dict(sys.modules, modules):
                        self.assertIsNone(mod.recover_choices(token, None, None, 'Reply', 'What next?',
                                                             dict(started=time.monotonic())))
                    self.assertEqual(token['choices_recovery']['reason'], reason)
                    self.assertTrue(token['choices_recovery']['parse_valid'])
                    self.assertFalse(token['choices_recovery']['staged'])
                    llm.chat.assert_called_once()

    def setup_story(self, root):
        fixture = stories.StoryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        mod = stories.module(root)
        mod.manager = fixture.manager(mod)
        mod.manager._load()
        mod.manager.state.update(status='offered', title='Notebook', summary='Find the notebook',
                                 participants=['sh'], turns=40, version=40)
        with open(mod.manager.path, 'w', encoding='utf-8') as stream:
            json.dump(mod.manager.state, stream)
        env, llm, _, modules = fixture.endpoint_env(root, mod, True)
        modules['config_loader'].cfg['story_events'].update(choices_enabled=True, intensity='high')
        # Eliminate the separate cameo classifier; this fixture tests only choices.
        env['resolve_cameo_intent'] = lambda *a: []
        return mod, env, llm, modules

    def test_due_missing_tag_recovery_display_selection_and_ack(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            mod, env, llm, modules = self.setup_story(root)
            before = copy.deepcopy(mod.manager.state)
            llm.chat.side_effect = ['We can discuss it later.', json.dumps(dict(options=OPTIONS))]
            with patch.dict(sys.modules, modules):
                result = env['chat'](dict(character='un', text='What next?', location='un_room',
                                          clock=dict(time='23:00', phase='night')))
            self.assertTrue(result['ok'])
            self.assertEqual(result['choices']['options'], OPTIONS)
            self.assertEqual(mod.manager.state, before)
            self.assertEqual(llm.chat.call_count, 2)
            call = llm.chat.call_args
            self.assertEqual(call.kwargs['override_max_tokens'], 384)
            self.assertEqual(call.kwargs['override_temperature'], .3)
            self.assertTrue(0 < call.kwargs['override_timeout'] <= 6)
            data = json.loads(call.args[0][1]['content'])
            self.assertEqual(data['story']['participants'], ['sh'])
            self.assertEqual(data['speaker'], 'un')
            self.assertEqual(data['location'], 'un_room')
            self.assertTrue(result['choices_recovery']['staged'])
            client = os.path.join(os.path.dirname(root), 'mod') if root == stories.DEV else os.path.dirname(root)
            client_env = clothing.ClothingTests().environment(client)
            clothing.load(os.path.join(client, 'es_ai_api.rpy'), client_env,
                          ['es_ai_sanitize_text', 'es_ai_story_choices_record',
                           'es_ai_story_choices_menu', 'es_ai_story_input_take'])
            client_env.update(ES_AI_STORY_INPUT=dict(pending=None, selection=None, choice=None),
                              ES_AI_FREE_SCENE=[True])
            client_env['renpy'].display_menu = lambda *a, **kw: 'details'
            client_env['es_ai_story_choices_record'](result['choices'])
            client_env['es_ai_story_choices_menu']()
            self.assertEqual(client_env['es_ai_story_input_take'](), OPTIONS[0]['text'])
            self.assertIsNone(mod.manager.latest_choice)
            mod.manager.acknowledge_direct([result['story_ack'], result['story_ack']])
            self.assertEqual(mod.manager.state['turns'], 41)
            self.assertEqual(mod.manager.state['decisions'], [])
            selection = dict(token=result['choices']['token'], version=41, id='details')
            self.assertIsNotNone(mod.manager.select_choice(selection, OPTIONS[0]['text']))

    def test_invalid_and_timeout_deliver_reply_without_reserving_cooldown(self):
        invalid = ['not JSON', '{"options":[]}', json.dumps(dict(options=OPTIONS[:1])),
                   json.dumps(dict(options=[OPTIONS[0], dict(id='x', text='[action:goto:beach]')])),
                   json.dumps(dict(options=[OPTIONS[0], dict(id='x', text='{b}yes{/b}')])),
                   json.dumps(dict(options=OPTIONS, goto='beach')), TimeoutError('offline timeout')]
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for response in invalid:
                with self.subTest(root=root, response=str(response)):
                    mod, env, llm, modules = self.setup_story(root)
                    llm.chat.side_effect = ['Ordinary reply', response]
                    with patch.dict(sys.modules, modules):
                        result = env['chat'](dict(character='un', text='What next?'))
                    self.assertTrue(result['ok'])
                    self.assertEqual(result['reply'], 'Ordinary reply')
                    self.assertNotIn('choices', result)
                    self.assertNotIn('goto', result)
                    self.assertEqual(llm.chat.call_count, 2)
                    self.assertEqual(result['choices_recovery']['status'],
                                     'timeout' if isinstance(response, Exception) else
                                     'no_decision' if response == '{"options":[]}' else 'invalid')
                    mod.manager.acknowledge_direct([result['story_ack']])
                    self.assertEqual(mod.manager.state['choice_signature'], '')
                    self.assertEqual(mod.manager.state['turns'], 41)

    def test_deferred_unrelated_task_allows_current_scene_decision(self):
        safe = [dict(id='talk', text='Let us sit and talk'),
                dict(id='subject', text='Let us change the subject')]
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for speaker in ('sl', 'un'):
                with self.subTest(root=root, speaker=speaker):
                    mod, env, llm, modules = self.setup_story(root)
                    mod.manager.state.update(status='active', title='Lost screwdriver',
                        summary='Shurik lost a screwdriver; help tomorrow in daylight.',
                        participants=['sh'], planned_time='tomorrow')
                    before = copy.deepcopy(mod.manager.state)
                    llm.chat.side_effect = ['I would rather just sit and talk. Shall we?',
                                            json.dumps(dict(options=safe))]
                    with patch.dict(sys.modules, modules):
                        result = env['chat'](dict(character=speaker, text='What shall we do?',
                            location='bus', clock=dict(time='23:00', phase='night')))
                    self.assertEqual(result['choices']['options'], safe)
                    self.assertTrue(result['choices_recovery']['staged'])
                    self.assertEqual(mod.manager.state, before)
                    prompt = llm.chat.call_args.args[0][0]['content']
                    self.assertIn('does NOT require every menu', prompt)
                    self.assertIn('Respect every boundary', prompt)
                    self.assertNotIn('Only the existing offered/active story', prompt)
                    mod.manager.acknowledge_direct([result['story_ack']])
                    self.assertEqual(mod.manager.state['status'], 'active')
                    self.assertEqual(mod.manager.state['summary'], before['summary'])
                    self.assertEqual(mod.manager.state['participants'], ['sh'])
                    self.assertEqual(mod.manager.state['planned_time'], 'tomorrow')
                    self.assertEqual(mod.manager.state['choice_turn'], 41)

    def test_skip_matrix_and_existing_valid_menu(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for reason in ('off', 'disabled', 'cooldown', 'inactive', 'declined', 'end', 'valid'):
                with self.subTest(root=root, reason=reason):
                    mod, env, llm, modules = self.setup_story(root)
                    cfg = modules['config_loader'].cfg['story_events']
                    text = 'What next?'
                    if reason == 'off':
                        cfg['choices_enabled'] = False
                    elif reason == 'disabled':
                        cfg['enabled'] = False
                    elif reason == 'cooldown':
                        mod.manager.state.update(choice_signature='previous', choice_turn=40)
                    elif reason == 'inactive':
                        mod.manager.state.update(status='inactive', offer_due=True)
                    elif reason == 'declined':
                        text = 'No thanks'
                    elif reason == 'end':
                        text = '\u041f\u043e\u043a\u0430, \u044f \u043f\u043e\u0448\u0451\u043b'
                    llm.chat.return_value = 'Ordinary reply' + (
                        ' [choices:' + json.dumps(dict(options=OPTIONS)) + ']' if reason == 'valid' else '')
                    with patch.dict(sys.modules, modules):
                        result = env['chat'](dict(character='un', text=text))
                    self.assertTrue(result['ok'])
                    llm.chat.assert_called_once()

    def test_concurrent_revision_and_budget_fail_closed(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for reason in ('stale', 'budget', 'late', 'toggle'):
                mod, env, llm, modules = self.setup_story(root)
                token = mod.manager.prepare(modules['config_loader'].cfg['story_events'], ['un', 'sh'], 'un')
                def generate(*a, **kw):
                    if reason == 'stale':
                        mod.manager.state['version'] += 1
                    if reason == 'toggle':
                        modules['config_loader'].cfg['story_events']['choices_enabled'] = False
                    return json.dumps(dict(options=OPTIONS))
                llm.chat.side_effect = generate
                with patch.dict(sys.modules, modules):
                    if reason == 'late':
                        ticks = iter([1, 1, 111])
                        with patch.object(mod.time, 'monotonic', side_effect=lambda: next(ticks, 112)):
                            result = mod.response_metadata(token, None, 'Reply', None, 'What next?',
                                recovery=dict(started=0))
                    else:
                        result = mod.response_metadata(token, None, 'Reply', None, 'What next?',
                            recovery=dict(started=time.monotonic() - (111 if reason == 'budget' else 0)))
                self.assertNotIn('choices', result)
                self.assertNotIn('choice_offer', token)
                self.assertEqual(llm.chat.call_count, 0 if reason == 'budget' else 1)

    def test_direct_recovery_durable_ack_once_and_no_random_recovery(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            mod, env, llm, modules = self.setup_story(root)
            with patch.dict(sys.modules, modules):
                token = mod.prepare(modules['config_loader'].cfg['story_events'], 'un')
                key = mod.manager.direct_request(token, 'Slavya, what next?', ['sl'], 'un')
                llm.chat.side_effect = ['Let us consider it.', json.dumps(dict(options=OPTIONS))]
                result = env['cameo'](dict(character='sl', active_id='un', mode='stay',
                    player_text='Slavya, what next?', story_token=key))
            self.assertEqual(llm.chat.call_count, 2)
            self.assertEqual(result['choices']['options'], OPTIONS)
            self.assertEqual(mod.manager.state['turns'], 40)
            fresh = mod.StoryManager(mod.manager.path)
            fresh.acknowledge_direct([result['story_ack'], result['story_ack']])
            self.assertEqual(fresh.state['turns'], 41)
            self.assertEqual(fresh.state['decisions'], [])
            llm.chat.reset_mock()
            llm.chat.side_effect = None
            llm.chat.return_value = 'Ordinary reply'
            with patch.dict(sys.modules, modules):
                result = env['cameo'](dict(character='sl', mode='stay'))
            llm.chat.assert_called_once()
            self.assertNotIn('choices_recovery', result)

    def test_new_offer_requires_primary_tag_and_duplicate_repair_once(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for opening in (False, True):
                mod, env, llm, modules = self.setup_story(root)
                if opening:
                    mod.manager.state.update(status='inactive', offer_due=True)
                    primary = 'Will you help? [story:{"status":"offered","title":"Task","summary":"Find notebook"}]'
                else:
                    token = mod.manager.prepare(modules['config_loader'].cfg['story_events'], ['un', 'sh'], 'un')
                    mod.manager.stage_choices(token, choices.OPTIONS, None, 'Reply')
                    mod.manager.commit(token, None, 'Reply')
                    mod.manager.state['turns'] += 1
                    primary = 'Another decision? [choices:' + json.dumps(dict(options=choices.OPTIONS)) + ']'
                llm.chat.side_effect = [primary, json.dumps(dict(options=OPTIONS))]
                with patch.dict(sys.modules, modules):
                    result = env['chat'](dict(character='un', text='What next?'))
                self.assertEqual(llm.chat.call_count, 2)
                self.assertEqual(result['choices']['options'], OPTIONS)

    def test_direct_departure_and_stale_recovery_never_show_menu(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for reason in ('leave', 'aside', 'stale'):
                mod, env, llm, modules = self.setup_story(root)
                with patch.dict(sys.modules, modules):
                    token = mod.prepare(modules['config_loader'].cfg['story_events'], 'un')
                    key = mod.manager.direct_request(token, 'Slavya, details?', ['sl'], 'un')
                    if reason == 'stale':
                        def generate(messages, **kw):
                            if kw.get('override_max_tokens') == 384:
                                mod.manager.state['version'] += 1
                                return json.dumps(dict(options=OPTIONS))
                            return 'Let us consider it.'
                        llm.chat.side_effect = generate
                    else:
                        llm.chat.return_value = 'Goodbye.' + (' [action:aside]' if reason == 'aside' else '')
                    result = env['cameo'](dict(character='sl', active_id='un', story_token=key,
                        player_text='Slavya, details?', mode='leave' if reason == 'leave' else 'stay'))
                self.assertFalse(result.get('choices'))
                self.assertEqual(llm.chat.call_count, 2 if reason == 'stale' else 1)


if __name__ == '__main__':
    unittest.main()
