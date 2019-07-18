from bdb import BdbQuit
import logging
from pathlib import Path
import yaml

import click

from gbd_mapping import causes
from vivarium_gbd_access.gbd import ARTIFACT_FOLDER
from vivarium_inputs import get_measure
from vivarium_inputs.data_artifact import utilities
from vivarium_inputs.data_artifact.cli import main
from vivarium_public_health.dataset_manager import Artifact

ASTHMA_DISMOD_ID = 1907  # Abie found from epiviz tool


@click.command()
@click.option('--append', '-a', is_flag=True,
              help="Preserve existing artifact and append to it")
@click.option('--verbose', '-v', is_flag=True,
              help="Turn on debug mode for logging")
@click.option('--pdb', 'debugger', is_flag=True, help='Drop the debugger if an error occurs')
def build_washout_artifact(append, verbose, debugger):
    """
    build_washout_artifact is a program for building data artifacts locally
    for the obesity_washout model.

    It will build an artifact for the ``vivarium_ihme_obesity_washout.yaml``
    model specification file stored in the repository.

    It requires access to the J drive and /ihme. If you are running this job
    from a qlogin on the cluster, you must specifically request J drive access
    when you qlogin by adding "-l archive=TRUE" to your command.

    Please have at least 30GB of memory on your qlogin."""
    model_specification = Path(__file__).parent.parent / 'model_specifications' / 'vivarium_ihme_obesity_washout.yaml'
    output_root = ARTIFACT_FOLDER / 'vivarium_ihme_obesity_washout'

    utilities.setup_logging(output_root, verbose, None, model_specification, append)

    try:
        main(str(model_specification), output_root, None, append)
        artifact_path = output_root / 'vivarium_ihme_obesity_washout.hdf'
        _patch_artifact(artifact_path, model_specification)
    except (BdbQuit, KeyboardInterrupt):
        raise
    except Exception as e:
        logging.exception("Uncaught exception: %s", e)
        if debugger:
            import pdb
            import traceback
            traceback.print_exc()
            pdb.post_mortem()
        else:
            raise


def _patch_artifact(artifact_path: Path, model_specification: Path):
    location = yaml.safe_load(model_specification.read_text())['configuration']['input_data']['location']
    asthma = causes.asthma
    asthma.dismod_id = ASTHMA_DISMOD_ID
    remission = get_measure(asthma, 'remission', location)
    # hdf files can't handle pandas.Interval objects
    remission = utilities.split_interval(remission, interval_column='age', split_column_prefix='age_group')
    remission = utilities.split_interval(remission, interval_column='year', split_column_prefix='year')

    art = Artifact(str(artifact_path))
    art.write(f'cause.{asthma.name}.remission', remission)
