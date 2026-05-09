<script lang="ts">
	import { goto } from '$app/navigation';
	$effect(() => { goto('/review', { replaceState: true }); });
</script>
