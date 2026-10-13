// Registers <cae-stat-tiles> and the <cae-count> it renders.
import { defineElement } from '../core/define.js';
import { CaeCount } from '../count/count.js';
import { CaeStatTiles } from '../tiles/stat-tiles.js';

defineElement('cae-stat-tiles', CaeStatTiles);
defineElement('cae-count', CaeCount);
