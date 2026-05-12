import type { Collection, ItemEntry, MetadataRecord, StatusCounts } from './types';

class AppState {
	collections: Collection[] = $state([]);
	selectedCollectionId: number | null = $state(null);
	statusFilter: string = $state('all');

	items: ItemEntry[] = $state([]);
	currentIndex: number = $state(0);
	currentMetadata: MetadataRecord | null = $state(null);

	stats: StatusCounts = $state({});

	saving: boolean = $state(false);
	revising: boolean = $state(false);
	panelOpen: boolean = $state(true);

	get currentItem(): ItemEntry | null {
		return this.items[this.currentIndex] ?? null;
	}

	get total(): number {
		return this.items.length;
	}

	get selectedCollection(): Collection | null {
		return this.collections.find(c => c.id === this.selectedCollectionId) ?? null;
	}
}

export const app = new AppState();
