from typing import Dict

import pandas as pd

from vivarium_public_health.metrics import MortalityObserver


class WashoutObserver(MortalityObserver):
    """Bins mortality observation by BMI and washes out deaths in a period."""

    def __init__(self):
        super().__init__()
        self.configuration_defaults['metrics'].update({
            'obesity_washout': {
                'bmi_bins': [0, 15, 18.5, 25, 30, 35, 40, 60, 200],
                'program_start': {
                    'year': 2000,
                    'month': 7,
                    'day': 9,
                },
                'duration': 5,  # years
            },
        })

    @property
    def name(self):
        return 'obesity_washout_observer'

    def setup(self, builder):
        super().setup(builder)

        self.washout_config = builder.configuration.metrics.obesity_washout

        self.program_start = pd.Timestamp(**self.washout_config.program_start.to_dict())
        if self.start_time > self.program_start:
            raise ValueError(f'The washout program must begin after the start of the simulation. '
                             f'Your simulation begins: {self.start_time} while the '
                             f'washout program begins {self.program_start}.')

        self.bmi_exposure = builder.value.get_value('high_body_mass_index_in_adults.exposure')
        self.bmi_groups = None

        builder.event.register_listener('collect_metrics', self.on_collect_metrics)

    def on_collect_metrics(self, event):
        if self.clock() < self.program_start <= event.time:
            pop = self.population_view.get(event.index, query='alive == "alive"')
            self.bmi_groups = self.split_bmi(pop.index)

    def split_bmi(self, index: pd.Index) -> Dict[str, pd.Index]:
        """Splits an index into groups based on BMI exposure.

        Parameters
        ----------
        index
            The population index to split.

        Returns
        -------
            A mapping between bmi group names and the index of the population
            in those bmi groups.

        """
        bmi = self.bmi_exposure(index)
        bins = self.washout_config.bmi_bins
        groups = {f'bmi_group_{lower}_to_{upper}': bmi.loc[(lower <= bmi) & (bmi < upper)].index
                  for lower, upper in zip(bins[:-1], bins[1:])}

        return groups

    def eligible(self, pop: pd.DataFrame) -> pd.Index:
        """Gets the observation eligible index."""
        duration = pd.Timedelta(days=self.washout_config.duration * 365.25)
        return pop.loc[(pop.exit_time >= self.program_start + duration)].index

    def metrics(self, index: pd.Index, metrics: Dict) -> Dict:
        pop = self.population_view.get(index)
        pop.loc[pop.exit_time.isnull(), 'exit_time'] = self.clock()

        for group, group_index in self.bmi_groups.items():
            eligble = self.eligble(pop.loc[group_index])
            m = super().metrics(eligble, {})
            m = {f'{k}_among_{group}': v for k, v in m.items()}
            metrics.update(m)

        return metrics
