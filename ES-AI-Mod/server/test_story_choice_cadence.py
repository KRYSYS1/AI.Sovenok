"""Delivered-exchange cadence and overdue story policy, entirely offline."""
import copy
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import test_story_events as stories
import test_delivery as delivery


OPTIONS = [dict(id='prepare', text='Compare the clues first'),
           dict(id='wait', text='Ask about another approach')]


class CadenceTests(unittest.TestCase):
    def setup_story(self, root, intensity='high'):
        directory = tempfile.TemporaryDirectory(dir=stories.TEMP)
        self.addCleanup(directory.cleanup)
        mod = stories.module(root)
        mod.manager = mod.StoryManager(os.path.join(directory.name, 'story.json'))
        mod.manager._load()
        mod.manager.state.update(status='active', title='Notebook', summary='Find the notebook',
                                 turns=40, version=40, participants=['sl'], planned_time='tomorrow')
        with open(mod.manager.path, 'w', encoding='utf-8') as stream:
            json.dump(mod.manager.state, stream)
        config = dict(enabled=True, choices_enabled=True, intensity=intensity)
        return mod, config

    def token(self, mod, config):
        return mod.manager.prepare(config, ['un', 'sl'], 'un')

    def metadata(self, mod, config, options=None, allow_choices=True):
        with patch.dict(sys.modules, config_loader=types.SimpleNamespace(cfg=dict(story_events=config))):
            return mod.response_metadata(self.token(mod, config), None, 'Let us consider the clues.',
                                         options, 'What next?', allow_choices=allow_choices)

    def test_exact_prospective_matrix_and_prompt(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for intensity, cadence in (('low', 6), ('medium', 3), ('high', 2)):
                with self.subTest(root=root, intensity=intensity):
                    mod, config = self.setup_story(root, intensity)
                    first = self.metadata(mod, config, OPTIONS)
                    self.assertIsNone(mod.manager.latest_choice)
                    self.assertEqual(mod.manager.state['turns'], 40)
                    mod.manager.acknowledge_direct([first['story_ack']])
                    self.assertEqual(mod.manager.state['choice_turn'], 41)
                    different = [dict(id='a', text='Check the map'), dict(id='b', text='Consult the schedule')]
                    for index in range(1, cadence + 1):
                        token = self.token(mod, config)
                        due = index == cadence
                        self.assertEqual(token['choice_due'], due)
                        self.assertEqual(token['choice_remaining'], cadence - index)
                        self.assertEqual('Choices are due in THIS response' in token['context'], due)
                        self.assertEqual('Choices are not due' in token['context'], not due)
                        if due:
                            self.assertIn('preparation or alternatives', token['context'])
                            self.assertIn('do not repeat offer/acceptance', token['context'])
                            self.assertIn('need not be a plot participant', token['context'])
                        before = copy.deepcopy(mod.manager.state)
                        response = self.metadata(mod, config, different)
                        self.assertEqual('choices' in response, due)
                        self.assertEqual(mod.manager.state, before)
                        mod.manager.acknowledge_direct([response['story_ack'], response['story_ack']])
                        self.assertEqual(mod.manager.state['turns'], 41 + index)
                    self.assertEqual(mod.manager.state['choice_turn'], 41 + cadence)

    def test_ordinary_show_ack_restart_once_and_failed_show(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            mod, config = self.setup_story(root)
            response = self.metadata(mod, config, OPTIONS)
            before = copy.deepcopy(mod.manager.state)
            client = os.path.join(os.path.dirname(root), 'mod') if root == stories.DEV else os.path.dirname(root)
            with tempfile.TemporaryDirectory(dir=stories.TEMP) as directory:
                env, _, _ = delivery.DeliveryTests().speech_env(client, directory)
                collected = []
                env['es_ai_story_choices_record'] = collected.append
                with self.assertRaises(RuntimeError):
                    env['es_ai_delivery_say'](delivery.DisplayCharacter(env['config'], fail=True),
                        'Reply', 'un', 'Reply', response['story_ack'], response['choices'])
                self.assertFalse(collected)
                self.assertEqual(mod.manager.state, before)
                self.assertIsNone(mod.manager.latest_choice)
                env['es_ai_delivery_say'](delivery.DisplayCharacter(env['config']), 'Reply', 'un', 'Reply',
                                         response['story_ack'], response['choices'])
                with open(env['es_ai_delivery_path'](), encoding='utf-8') as stream:
                    ack = json.load(stream)['story_acks'][0]
                self.assertEqual(collected, [response['choices']])
                fresh = mod.StoryManager(mod.manager.path)
                fresh.acknowledge_direct([ack, ack])
                self.assertEqual(fresh.state['turns'], before['turns'] + 1)
                menu = response['choices']
                self.assertIsNotNone(fresh.select_choice(dict(token=menu['token'], version=menu['version'], id='prepare'), OPTIONS[0]['text']))
                restarted = mod.StoryManager(mod.manager.path)
                restarted.acknowledge_direct([ack])
                restarted.prepare(config, ['un', 'sl'], 'un')
                self.assertEqual(restarted.state, fresh.state)

    def test_mixed_primary_direct_and_selected_share_cadence(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            mod, config = self.setup_story(root)
            first = self.metadata(mod, config, OPTIONS)
            mod.manager.acknowledge_direct([first['story_ack']])
            token = self.token(mod, config)
            self.assertFalse(token['choice_due'])
            key = mod.manager.direct_request(token, 'Slavya, what next?', ['sl'], 'un')
            ack = mod.manager.direct_delivery(key, 'sl', 'un', 'Slavya, what next?', None, 'We can compare notes.')
            self.assertEqual(mod.manager.state['turns'], 41)
            mod.manager.acknowledge_direct([ack, ack])
            self.assertEqual(mod.manager.state['turns'], 42)
            self.assertTrue(self.token(mod, config)['choice_due'])
            different = [dict(id='a', text='Read the notes together'), dict(id='b', text='Wait for tomorrow')]
            second = self.metadata(mod, config, different)
            mod.manager.acknowledge_direct([second['story_ack']])
            menu = second['choices']
            token = self.token(mod, config)
            cfg = types.SimpleNamespace(cfg=dict(story_events=config))
            with patch.dict(sys.modules, config_loader=cfg):
                mod.bind_selection(token, dict(token=menu['token'], version=menu['version'], id='a'), different[0]['text'])
                result = mod.response_metadata(token, None, 'Let us read.', None, different[0]['text'])
            self.assertEqual(mod.manager.state['turns'], 43)
            mod.manager.acknowledge_direct([result['story_ack'], result['story_ack']])
            self.assertEqual(mod.manager.state['turns'], 44)
            self.assertEqual(mod.manager.state['decisions'], [different[0]])
            self.assertTrue(self.token(mod, config)['choice_due'])

    def test_actual_end_response_does_not_reserve_choice_cooldown(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            mod, config = self.setup_story(root)
            env, llm, _, modules = stories.StoryTests().endpoint_env(root, mod, True)
            modules['config_loader'].cfg['story_events'].update(config)
            llm.chat.return_value = 'Goodbye. [choices:' + json.dumps(dict(options=OPTIONS)) + ']'
            with patch.dict(sys.modules, modules):
                result = env['chat'](dict(character='un', text='\u041f\u043e\u043a\u0430, \u044f \u043f\u043e\u0448\u0451\u043b', scene=dict(present=['un'])))
            self.assertTrue(result.get('end_conversation'), result)
            self.assertNotIn('choices', result)
            self.assertEqual(mod.manager.state['turns'], 40)
            mod.manager.acknowledge_direct([result['story_ack']])
            self.assertEqual(mod.manager.state['turns'], 41)
            self.assertEqual(mod.manager.state['choice_signature'], '')
            self.assertTrue(self.token(mod, config)['choice_due'])
            llm.chat.assert_called_once()

    def test_missing_duplicate_suppressed_and_stale_do_not_reserve_menu(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            mod, config = self.setup_story(root)
            missing = self.metadata(mod, config)
            mod.manager.acknowledge_direct([missing['story_ack']])
            self.assertTrue(self.token(mod, config)['choice_due'])
            suppressed = self.metadata(mod, config, OPTIONS, False)
            self.assertNotIn('choices', suppressed)
            mod.manager.acknowledge_direct([suppressed['story_ack']])
            self.assertEqual(mod.manager.state['choice_signature'], '')
            staged = self.metadata(mod, config, OPTIONS)
            mod.manager.acknowledge_direct([staged['story_ack']])
            mod.manager.acknowledge_direct([self.metadata(mod, config)['story_ack']])
            duplicate = self.metadata(mod, config, list(reversed(OPTIONS)))
            self.assertNotIn('choices', duplicate)
            mod.manager.acknowledge_direct([duplicate['story_ack']])
            self.assertTrue(self.token(mod, config)['choice_due'])
            other = [dict(id='a', text='Read the margin notes'), dict(id='b', text='Wait for more evidence')]
            stale = self.metadata(mod, config, other)
            mod.manager.acknowledge_direct([self.metadata(mod, config)['story_ack']])
            before = copy.deepcopy(mod.manager.state)
            mod.manager.acknowledge_direct([stale['story_ack']])
            self.assertEqual(mod.manager.state, before)
            self.assertTrue(self.token(mod, config)['choice_due'])

    def test_terminal_bound_pause_and_same_labels_new_story(self):
        for root in stories.existing_paths((stories.DEV, stories.WORKSHOP)):
            for intensity, maximum in (('high', 8), ('medium', 12), ('low', 20)):
                for status in ('completed', 'declined'):
                    mod, config = self.setup_story(root, intensity)
                    first = self.metadata(mod, config, OPTIONS)
                    mod.manager.acknowledge_direct([first['story_ack']])
                    mod.manager.state.update(status=status, closed_turn=41)
                    for elapsed in range(10):
                        mod.manager.state['turns'] = 41 + elapsed
                        self.assertFalse(self.token(mod, config)['eligible'])
                    mod.manager.state['turns'] = 41 + 10 + maximum
                    token = self.token(mod, config)
                    self.assertTrue(token['eligible'])
                    self.assertEqual(token['offer_reason'], 'overdue')
                    update = dict(status='offered', title='New task', summary='A new public discovery')
                    menu = mod.manager.stage_choices(token, OPTIONS, update, 'Another task?')
                    self.assertIsNotNone(menu)
                    self.assertTrue(mod.manager.commit(token, update, 'Another task?'))
                    self.assertEqual(mod.manager.state['status'], 'offered')
                    self.assertEqual(mod.manager.state['decisions'], [])


if __name__ == '__main__':
    unittest.main()
