import pandas as pd

from vivarium_public_health.disease import DiseaseModel, RiskAttributableDisease
from vivarium_public_health.metrics.utilities import get_age_bins, get_person_time, get_deaths, get_years_of_life_lost


class BMIObserver:
    configuration_defaults = {
        'metrics': {
            'bmi': {
                'by_age': False,
                'by_year': False,
                'by_sex': False,
                'washout': {
                    'program_start': {
                        'month': 7,
                        'day': 9,
                        'year': 2000
                    },
                    'duration': 5  # years
                }
            }
        }
    }

    @property
    def name(self):
        return 'bmi_observer'

    def setup(self, builder):
        self.config = builder.configuration.metrics.bmi
        self.clock = builder.time.clock()
        self.step_size = builder.time.step_size()
        self.start_time = self.clock()

        program_start = pd.Timestamp(month=self.config.washout.program_start.month,
                                     day=self.config.washout.program_start.day,
                                     year=self.config.washout.program_start.year)
        if self.start_time > program_start:
            raise ValueError(f'The washout program must begin after the start of the simulation. '
                             f'Your simulation begins: {self.start_time} while the '
                             f'washout program begins {program_start}.')

        self.washout_period_end = program_start + pd.Timedelta(days=self.config.washout.duration*365.25)

        self.initial_pop_entrance_time = self.start_time - self.step_size()
        self.age_bins = get_age_bins(builder)
        diseases = builder.components.get_components_by_type((DiseaseModel, RiskAttributableDisease))
        self.causes = [c.state_column for c in diseases] + ['other_causes']

        life_expectancy_data = builder.data.load("population.theoretical_minimum_risk_life_expectancy")
        self.life_expectancy = builder.lookup.build_table(life_expectancy_data, key_columns=[],
                                                          parameter_columns=[('age', 'age_group_start',
                                                                              'age_group_end')])

        self.bmi_exposure = builder.value.get_value('high_body_mass_index_in_adults.exposure')

        columns_required = ['tracked', 'alive', 'entrance_time', 'exit_time', 'cause_of_death',
                            'years_of_life_lost', 'age']
        if self.config.by_sex:
            columns_required += ['sex']
        self.population_view = builder.population.get_view(columns_required)

        builder.value.register_value_modifier('metrics', self.metrics)

    @staticmethod
    def get_bmi_categories():
        # TODO: verify bmi exposure is in kg/m2
        # TODO: verify range of bmi exposure
        thresholds = [15, 18.5, 25, 30, 35, 40, 60]
        names = ['underweight', 'normal', 'overweight', 'obesity_grade_1', 'obesity_grade_2', 'obesity_grade_3']
        return names, thresholds

    def metrics(self, index: pd.Index, metrics: dict):
        pop = self.population_view.get(index)
        pop.loc[pop.exit_time.isnull(), 'exit_time'] = self.clock()

        pop = pop[pop.exit_time < self.washout_period_end]

        exposure = self.bmi_exposure(index)
        names, thresholds = self.get_bmi_categories()
        bmi_categories = pd.cut(exposure, thresholds, right=False, labels=names)

        for cat in bmi_categories.unique():
            cat_pop = pop.loc[bmi_categories[bmi_categories == cat].index, :]
            person_time = get_person_time(cat_pop, self.config.to_dict(), self.start_time, self.clock(), self.age_bins)
            deaths = get_deaths(cat_pop, self.config.to_dict(), self.start_time, self.clock(), self.age_bins, self.causes)
            ylls = get_years_of_life_lost(cat_pop, self.config.to_dict(), self.start_time, self.clock(),
                                          self.age_bins, self.life_expectancy, self.causes)

            person_time = {f'{k}_{cat}': v for k, v in person_time.items()}
            deaths = {f'{k}_{cat}': v for k, v in deaths.items()}
            ylls = {f'{k}_{cat}': v for k, v in ylls.items()}

            metrics.update(person_time)
            metrics.update(deaths)
            metrics.update(ylls)

        the_living = pop[(pop.alive == 'alive') & pop.tracked]
        the_dead = pop[pop.alive == 'dead']
        metrics['years_of_life_lost'] = self.life_expectancy(the_dead.index).sum()
        metrics['total_population_living'] = len(the_living)
        metrics['total_population_dead'] = len(the_dead)

        return metrics