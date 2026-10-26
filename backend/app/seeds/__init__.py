"""
Seed Infrastructure for LMS Backend Application.

This module provides a base seed runner pattern for populating the database
with initial data. Seeds can be run via CLI: python -m app.seed

Usage:
    python -m app.seed              # Run all seeds
    python -m app.seed --reset    # Reset and re-run all seeds
"""

import argparse
import asyncio
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.extensions import AsyncSessionLocal, init_db


@dataclass
class SeedResult:
    """Result of a seed operation."""
    name: str
    success: bool
    message: str
    records_created: int = 0


class BaseSeed(ABC):
    """
    Abstract base class for database seeds.
    
    All seed classes should inherit from this and implement the `run` method.
    
    Example:
        class UserSeed(BaseSeed):
            name = "users"
            
            async def run(self, session: AsyncSession) -> SeedResult:
                # Create users...
                return SeedResult(name=self.name, success=True, message="Created users", records_created=5)
    """
    
    name: str = "base"
    priority: int = 100  # Lower numbers run first
    
    @abstractmethod
    async def run(self, session: AsyncSession) -> SeedResult:
        """
        Execute the seed operation.
        
        Args:
            session: Async database session
            
        Returns:
            SeedResult: Result of the seed operation
        """
        pass
    
    async def should_run(self, session: AsyncSession) -> bool:
        """
        Check if this seed should run.
        
        Override this to implement conditional seeding logic.
        
        Args:
            session: Async database session
            
        Returns:
            bool: True if seed should run, False otherwise
        """
        return True
    
    async def cleanup(self, session: AsyncSession) -> None:
        """
        Clean up existing data before seeding.
        
        Override this to implement cleanup logic when --reset is used.
        
        Args:
            session: Async database session
        """
        pass


class SeedRunner:
    """
    Runner for executing database seeds.
    
    Manages the registration and execution of seed classes.
    """
    
    def __init__(self):
        self.seeds: List[type[BaseSeed]] = []
    
    def register(self, seed_class: type[BaseSeed]) -> type[BaseSeed]:
        """
        Register a seed class.
        
        Can be used as a decorator:
            @seed_runner.register
            class UserSeed(BaseSeed):
                ...
        
        Args:
            seed_class: Seed class to register
            
        Returns:
            The registered seed class (for decorator use)
        """
        self.seeds.append(seed_class)
        # Sort by priority
        self.seeds.sort(key=lambda s: s.priority)
        return seed_class
    
    async def run_all(
        self,
        reset: bool = False,
        only: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None
    ) -> List[SeedResult]:
        """
        Run all registered seeds.
        
        Args:
            reset: If True, clean up existing data before seeding
            only: List of seed names to run (if None, run all)
            exclude: List of seed names to skip
            
        Returns:
            List[SeedResult]: Results of all seed operations
        """
        results: List[SeedResult] = []
        
        async with AsyncSessionLocal() as session:
            for seed_class in self.seeds:
                seed_name = seed_class.name
                
                # Skip if not in only list
                if only and seed_name not in only:
                    continue
                
                # Skip if in exclude list
                if exclude and seed_name in exclude:
                    continue
                
                # Create seed instance
                seed = seed_class()
                
                # Check if should run
                should_run = await seed.should_run(session)
                if not should_run:
                    results.append(SeedResult(
                        name=seed_name,
                        success=True,
                        message="Skipped (already exists)"
                    ))
                    continue
                
                # Clean up if reset
                if reset:
                    try:
                        await seed.cleanup(session)
                        await session.commit()
                    except Exception as e:
                        await session.rollback()
                        results.append(SeedResult(
                            name=seed_name,
                            success=False,
                            message=f"Cleanup failed: {e}"
                        ))
                        continue
                
                # Run seed
                try:
                    result = await seed.run(session)
                    await session.commit()
                    results.append(result)
                except Exception as e:
                    await session.rollback()
                    results.append(SeedResult(
                        name=seed_name,
                        success=False,
                        message=f"Seed failed: {e}"
                    ))
        
        return results


# Global seed runner instance
seed_runner = SeedRunner()


async def run_seeds(
    reset: bool = False,
    only: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None
) -> List[SeedResult]:
    """
    Run all registered seeds.
    
    This is the main entry point for running seeds programmatically.
    
    Args:
        reset: If True, clean up existing data before seeding
        only: List of seed names to run (if None, run all)
        exclude: List of seed names to skip
        
    Returns:
        List[SeedResult]: Results of all seed operations
    """
    # Import seed modules to register them
    # This will be populated as domain seeds are created
    try:
        from app.seeds import users, courses, enrollments
    except ImportError:
        pass  # Seed modules may not exist yet
    
    return await seed_runner.run_all(reset=reset, only=only, exclude=exclude)


def print_results(results: List[SeedResult]) -> None:
    """Print seed results in a formatted table."""
    print("\n" + "=" * 70)
    print("SEED RESULTS")
    print("=" * 70)
    
    for result in results:
        status = "✅" if result.success else "❌"
        records = f" ({result.records_created} records)" if result.records_created > 0 else ""
        print(f"{status} {result.name:<20} {result.message}{records}")
    
    success_count = sum(1 for r in results if r.success)
    total_count = len(results)
    
    print("-" * 70)
    print(f"Total: {success_count}/{total_count} seeds successful")
    print("=" * 70 + "\n")


def main() -> int:
    """
    CLI entry point for seed runner.
    
    Returns:
        int: Exit code (0 for success, 1 for any failures)
    """
    settings = get_settings()
    
    parser = argparse.ArgumentParser(
        prog="python -m app.seed",
        description="LMS Database Seed Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m app.seed              # Run all seeds
  python -m app.seed --reset      # Reset and re-run all seeds
  python -m app.seed --only users # Run only user seeds
  python -m app.seed --exclude test # Skip test seeds
        """
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clean up existing data before seeding"
    )
    parser.add_argument(
        "--only",
        type=str,
        help="Comma-separated list of seed names to run"
    )
    parser.add_argument(
        "--exclude",
        type=str,
        help="Comma-separated list of seed names to skip"
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Initialize database tables before seeding"
    )
    
    args = parser.parse_args()
    
    # Parse only/exclude lists
    only = [s.strip() for s in args.only.split(",")] if args.only else None
    exclude = [s.strip() for s in args.exclude.split(",")] if args.exclude else None
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           LMS Database Seed Runner                           ║
╠══════════════════════════════════════════════════════════════╣
║  Environment:  {settings.environment:<46} ║
║  Reset Mode:   {str(args.reset):<46} ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    async def run():
        # Initialize database if requested
        if args.init_db:
            print("📦 Initializing database tables...")
            await init_db()
            print("✅ Database initialized\n")
        
        # Run seeds
        results = await run_seeds(reset=args.reset, only=only, exclude=exclude)
        print_results(results)
        
        # Return exit code
        return 0 if all(r.success for r in results) else 1
    
    try:
        exit_code = asyncio.run(run())
        return exit_code
    except KeyboardInterrupt:
        print("\n\n👋 Seed runner stopped by user.")
        return 0
    except Exception as e:
        print(f"\n❌ Seed runner error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
